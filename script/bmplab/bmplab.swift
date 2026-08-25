#!/usr/bin/env swift

import Cocoa
import ImageIO

// ---------------------------------------------------------------------------
// bmplab.swift — interactive BMP glitch lab.
//
//   swiftc bmplab.swift -o bmplab
//   ./bmplab <image.bmp>
//
// Side-by-side original vs. glitched BMP preview with four controls:
//   - Pixel Data: corrupt bytes in the pixel array
//   - Color Depth: rewrite the DIB header bits-per-pixel field
//   - Dimensions: rewrite the DIB width/height fields
//   - Header: perturb a few header values without breaking the file outright
// ---------------------------------------------------------------------------

struct SplitMix64: RandomNumberGenerator {
    var state: UInt64
    init(seed: UInt64) { state = seed }
    mutating func next() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
}

func die(_ msg: String) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(1)
}

func readUInt16LE(_ bytes: [UInt8], offset: Int) -> UInt16 {
    guard offset >= 0, offset + 1 < bytes.count else { return 0 }
    return UInt16(bytes[offset]) | (UInt16(bytes[offset + 1]) << 8)
}

func readUInt32LE(_ bytes: [UInt8], offset: Int) -> UInt32 {
    guard offset >= 0, offset + 3 < bytes.count else { return 0 }
    return UInt32(bytes[offset]) |
    (UInt32(bytes[offset + 1]) << 8) |
    (UInt32(bytes[offset + 2]) << 16) |
    (UInt32(bytes[offset + 3]) << 24)
}

func writeUInt16LE(_ value: UInt16, to bytes: inout [UInt8], offset: Int) -> Bool {
    guard offset >= 0, offset + 1 < bytes.count else { return false }
    bytes[offset] = UInt8(value & 0xFF)
    bytes[offset + 1] = UInt8((value >> 8) & 0xFF)
    return true
}

func writeUInt32LE(_ value: UInt32, to bytes: inout [UInt8], offset: Int) -> Bool {
    guard offset >= 0, offset + 3 < bytes.count else { return false }
    bytes[offset] = UInt8(value & 0xFF)
    bytes[offset + 1] = UInt8((value >> 8) & 0xFF)
    bytes[offset + 2] = UInt8((value >> 16) & 0xFF)
    bytes[offset + 3] = UInt8((value >> 24) & 0xFF)
    return true
}

struct BMPAnalysis {
    let fileHeaderOffset = 0
    let dibHeaderOffset = 14
    let fileSize: UInt32
    let pixelDataOffset: Int
    let dibHeaderSize: UInt32
    let width: Int32
    let height: Int32
    let bitsPerPixel: UInt16
    let rowSize: Int
    let pixelArrayLength: Int
    let pixelArrayRange: Range<Int>
}

func parseBMP(_ bytes: [UInt8]) -> BMPAnalysis? {
    guard bytes.count >= 54 else { return nil }
    guard bytes[0] == 0x42, bytes[1] == 0x4D else { return nil }

    let fileSize = readUInt32LE(bytes, offset: 2)
    let pixelDataOffset = Int(readUInt32LE(bytes, offset: 10))
    let dibHeaderSize = readUInt32LE(bytes, offset: 14)
    guard pixelDataOffset >= 14, pixelDataOffset <= bytes.count else { return nil }

    let width = Int32(readUInt32LE(bytes, offset: 18))
    let height = Int32(readUInt32LE(bytes, offset: 22))
    let bitsPerPixel = readUInt16LE(bytes, offset: 28)

    let widthAbs = max(1, Int(abs(width)))
    let heightAbs = max(1, Int(abs(height)))
    let rowSize = ((widthAbs * Int(bitsPerPixel) + 31) / 32) * 4
    let pixelArrayLength = max(0, min(bytes.count - pixelDataOffset, rowSize * heightAbs))
    let pixelArrayRange = pixelDataOffset..<(pixelDataOffset + pixelArrayLength)

    return BMPAnalysis(
        fileSize: fileSize,
        pixelDataOffset: pixelDataOffset,
        dibHeaderSize: dibHeaderSize,
        width: width,
        height: height,
        bitsPerPixel: bitsPerPixel,
        rowSize: rowSize,
        pixelArrayLength: pixelArrayLength,
        pixelArrayRange: pixelArrayRange
    )
}

func loadImage(from data: Data) -> NSImage? {
    guard data.count >= 54 else { return nil }

    let bytes = [UInt8](data)
    guard bytes.count >= 54, bytes[0] == 0x42, bytes[1] == 0x4D else { return nil }

    let pixelDataOffset = Int(readUInt32LE(bytes, offset: 10))
    guard pixelDataOffset >= 14, pixelDataOffset <= bytes.count else { return nil }

    let width = Int32(readUInt32LE(bytes, offset: 18))
    let height = Int32(readUInt32LE(bytes, offset: 22))
    let bitsPerPixel = Int(readUInt16LE(bytes, offset: 28))
    guard abs(width) > 0, abs(height) > 0, abs(width) <= 16_384, abs(height) <= 16_384, bitsPerPixel > 0, bitsPerPixel <= 32 else {
        return nil
    }

    if let src = CGImageSourceCreateWithData(data as CFData, nil),
       let cg = CGImageSourceCreateImageAtIndex(src, 0, [kCGImageSourceShouldCache: true] as CFDictionary) {
        return NSImage(cgImage: cg, size: NSSize(width: cg.width, height: cg.height))
    }
    return nil
}

final class BMPGlitchModel {
    let original: [UInt8]
    let analysis: BMPAnalysis

    init(data: Data) {
        self.original = [UInt8](data)
        let fallbackOffset = min(54, max(0, self.original.count))
        self.analysis = parseBMP(self.original) ?? BMPAnalysis(
            fileSize: UInt32(self.original.count),
            pixelDataOffset: fallbackOffset,
            dibHeaderSize: 40,
            width: 1,
            height: 1,
            bitsPerPixel: 24,
            rowSize: 4,
            pixelArrayLength: max(0, self.original.count - fallbackOffset),
            pixelArrayRange: fallbackOffset..<(fallbackOffset)
        )
    }

    func render(pixelAmount: Double, colorDepthIndex: Int, dimensionAmount: Double, headerAmount: Double, seed: UInt64) -> (data: Data, changed: Int) {
        var bytes = original
        var rng = SplitMix64(seed: seed)

        let pixelArray = analysis.pixelArrayRange
        let pixelBudget = pixelArray.isEmpty ? 0 : max(0, Int(round(pixelAmount / 100.0 * Double(max(1, pixelArray.count)) * 0.35)))
        for _ in 0..<pixelBudget {
            guard !pixelArray.isEmpty, pixelArray.count > 0 else { break }
            let idx = pixelArray.lowerBound + Int(rng.next() % UInt64(pixelArray.count))
            if idx >= bytes.count { continue }
            let value = UInt8(rng.next() & 0xFF)
            bytes[idx] = value
        }

        let colorDepths: [UInt16] = [1, 4, 8, 16, 24, 32]
        let targetDepth = colorDepths[min(colorDepthIndex, colorDepths.count - 1)]
        _ = writeUInt16LE(targetDepth, to: &bytes, offset: analysis.dibHeaderOffset + 14)

        let dimensionScale = max(0.25, min(4.0, 1.0 + (dimensionAmount / 100.0) * 2.0))
        let newWidth = max(1, min(16_384, Int32(round(Double(abs(analysis.width)) * dimensionScale))))
        let newHeight = max(1, min(16_384, Int32(round(Double(abs(analysis.height)) * dimensionScale))))
        _ = writeUInt32LE(UInt32(newWidth), to: &bytes, offset: analysis.dibHeaderOffset + 4)
        _ = writeUInt32LE(UInt32(newHeight), to: &bytes, offset: analysis.dibHeaderOffset + 8)

        let headerSteps = max(0, Int(round(headerAmount / 100.0 * 12.0)))
        for _ in 0..<headerSteps {
            switch Int(rng.next() % 4) {
            case 0:
                let delta = Int(rng.next() % 33) - 16
                let oldValue = Int(readUInt32LE(bytes, offset: 2))
                let clamped = UInt32(max(14, min(bytes.count, oldValue + delta)))
                _ = writeUInt32LE(clamped, to: &bytes, offset: 2)
            case 1:
                let delta = Int(rng.next() % 33) - 16
                let oldValue = Int(readUInt32LE(bytes, offset: 10))
                let clamped = UInt32(max(14, min(bytes.count, oldValue + delta)))
                _ = writeUInt32LE(clamped, to: &bytes, offset: 10)
            case 2:
                guard bytes.count > 7 else { continue }
                bytes[6] = bytes[6] &+ UInt8(rng.next() % 8)
                bytes[7] = bytes[7] &+ UInt8(rng.next() % 8)
            default:
                let idx = 14 + Int(rng.next() % 8)
                if idx < bytes.count {
                    bytes[idx] = bytes[idx] &+ UInt8(rng.next() % 16)
                }
            }
        }

        let changed = pixelBudget + headerSteps
        return (Data(bytes), changed)
    }
}

func makeLabel(_ text: String, width: CGFloat? = nil, bold: Bool = false) -> NSTextField {
    let f = NSTextField(labelWithString: text)
    f.font = bold ? .boldSystemFont(ofSize: 12) : .systemFont(ofSize: 12)
    if let w = width {
        f.translatesAutoresizingMaskIntoConstraints = false
        f.widthAnchor.constraint(equalToConstant: w).isActive = true
    }
    return f
}

final class Controller: NSObject {
    let model: BMPGlitchModel
    let inputPath: String

    var pixelAmount: Double = 0
    var colorDepthIndex: Int = 4
    var dimensionAmount: Double = 0
    var headerAmount: Double = 0
    var lastData: Data

    let originalView = NSImageView()
    let glitchedView = NSImageView()
    var pixelValueLabel = makeLabel("")
    var colorValueLabel = makeLabel("")
    var dimensionValueLabel = makeLabel("")
    var headerValueLabel = makeLabel("")
    var statusLabel = makeLabel("")

    init(model: BMPGlitchModel, inputPath: String) {
        self.model = model
        self.inputPath = inputPath
        self.lastData = Data(model.original)
        super.init()
    }

    func buildWindow() -> NSWindow {
        let originalImage = loadImage(from: Data(model.original))
        originalView.image = originalImage

        let imagesRow = NSStackView(views: [
            imageColumn(title: "ORIGINAL", view: originalView),
            imageColumn(title: "GLITCHED", view: glitchedView)
        ])
        imagesRow.orientation = .horizontal
        imagesRow.spacing = 16
        imagesRow.alignment = .top

        let pixelSlider = NSSlider(value: pixelAmount, minValue: 0, maxValue: 100, target: self, action: #selector(pixelChanged(_:)))
        let colorSlider = NSSlider(value: Double(colorDepthIndex), minValue: 0, maxValue: 5, target: self, action: #selector(colorDepthChanged(_:)))
        colorSlider.numberOfTickMarks = 6
        let dimensionSlider = NSSlider(value: dimensionAmount, minValue: -100, maxValue: 100, target: self, action: #selector(dimensionsChanged(_:)))
        let headerSlider = NSSlider(value: headerAmount, minValue: 0, maxValue: 100, target: self, action: #selector(headerChanged(_:)))

        let controlRows: [NSView] = [
            sliderRow(name: "pixel data", slider: pixelSlider, trailing: pixelValueLabel),
            sliderRow(name: "color depth", slider: colorSlider, trailing: colorValueLabel),
            sliderRow(name: "dimensions", slider: dimensionSlider, trailing: dimensionValueLabel),
            sliderRow(name: "header", slider: headerSlider, trailing: headerValueLabel)
        ]

        let randomButton = NSButton(title: "Random", target: self, action: #selector(randomize))
        let saveButton = NSButton(title: "Save glitched…", target: self, action: #selector(save))
        let bottomRow = NSStackView(views: [randomButton, saveButton, statusLabel])
        bottomRow.orientation = .horizontal
        bottomRow.spacing = 12

        let controlsStack = NSStackView(views: controlRows + [bottomRow])
        controlsStack.orientation = .vertical
        controlsStack.alignment = .leading
        controlsStack.spacing = 8

        let separator = NSBox()
        separator.boxType = .separator
        separator.translatesAutoresizingMaskIntoConstraints = false
        separator.widthAnchor.constraint(equalToConstant: 688).isActive = true

        let main = NSStackView(views: [imagesRow, separator, controlsStack])
        main.orientation = .vertical
        main.alignment = .leading
        main.spacing = 14
        main.translatesAutoresizingMaskIntoConstraints = false

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 720, height: 760),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        window.title = "BMPlab — \((inputPath as NSString).lastPathComponent)"
        window.center()

        let content = window.contentView!
        content.addSubview(main)
        NSLayoutConstraint.activate([
            main.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 16),
            main.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -16),
            main.topAnchor.constraint(equalTo: content.topAnchor, constant: 16),
            main.bottomAnchor.constraint(lessThanOrEqualTo: content.bottomAnchor, constant: -16)
        ])

        recompute()
        return window
    }

    private func imageColumn(title: String, view: NSImageView) -> NSView {
        view.imageScaling = .scaleProportionallyUpOrDown
        view.wantsLayer = true
        view.layer?.backgroundColor = NSColor.black.cgColor
        view.translatesAutoresizingMaskIntoConstraints = false
        view.widthAnchor.constraint(equalToConstant: 330).isActive = true
        view.heightAnchor.constraint(equalToConstant: 440).isActive = true
        let col = NSStackView(views: [makeLabel(title, bold: true), view])
        col.orientation = .vertical
        col.alignment = .centerX
        col.spacing = 6
        return col
    }

    private func sliderRow(name: String, slider: NSSlider, trailing: NSView) -> NSStackView {
        slider.translatesAutoresizingMaskIntoConstraints = false
        slider.widthAnchor.constraint(equalToConstant: 300).isActive = true
        let row = NSStackView(views: [makeLabel(name, width: 90), slider, trailing])
        row.orientation = .horizontal
        row.spacing = 10
        return row
    }

    @objc private func pixelChanged(_ sender: NSSlider) {
        pixelAmount = sender.doubleValue
        recompute()
    }

    @objc private func colorDepthChanged(_ sender: NSSlider) {
        colorDepthIndex = Int(sender.doubleValue.rounded())
        recompute()
    }

    @objc private func dimensionsChanged(_ sender: NSSlider) {
        dimensionAmount = sender.doubleValue
        recompute()
    }

    @objc private func headerChanged(_ sender: NSSlider) {
        headerAmount = sender.doubleValue
        recompute()
    }

    @objc private func randomize() {
        pixelAmount = Double.random(in: 0...100)
        colorDepthIndex = Int.random(in: 0...5)
        dimensionAmount = Double.random(in: -100...100)
        headerAmount = Double.random(in: 0...100)
        recompute()
    }

    @objc private func save() {
        let panel = NSSavePanel()
        let baseName = ((inputPath as NSString).deletingPathExtension as NSString).lastPathComponent
        panel.nameFieldStringValue = baseName + ".glitch.bmp"
        if panel.runModal() == .OK, let url = panel.url {
            try? lastData.write(to: url)
            statusLabel.stringValue = "Saved \(url.lastPathComponent)"
        }
    }

    private func recompute() {
        let colorDepths: [UInt16] = [1, 4, 8, 16, 24, 32]
        let targetDepth = colorDepths[min(colorDepthIndex, colorDepths.count - 1)]
        let result = model.render(pixelAmount: pixelAmount, colorDepthIndex: colorDepthIndex, dimensionAmount: dimensionAmount, headerAmount: headerAmount, seed: UInt64(pixelsToSeed()))
        lastData = result.data
        let image = loadImage(from: result.data)
        glitchedView.image = image

        pixelValueLabel.stringValue = String(format: "%.0f%%", pixelAmount)
        colorValueLabel.stringValue = "\(targetDepth) bit"
        dimensionValueLabel.stringValue = String(format: "%.0f%%", dimensionAmount)
        headerValueLabel.stringValue = String(format: "%.0f%%", headerAmount)
        statusLabel.stringValue = image == nil ? "preview skipped · \(result.changed) changes" : "\(result.changed) changes · \(lastData.count) B"
    }

    private func pixelsToSeed() -> Int {
        Int(round(pixelAmount * 10 + Double(colorDepthIndex) * 31 + dimensionAmount * 2 + headerAmount * 5))
    }
}

let args = CommandLine.arguments
guard args.count >= 2 else { die("Usage: bmplab <image.bmp>") }
let inputPath = args[1]
guard let data = FileManager.default.contents(atPath: inputPath) else {
    die("Could not read file: \(inputPath)")
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)

let mainMenu = NSMenu()
let appItem = NSMenuItem()
mainMenu.addItem(appItem)
let appSubmenu = NSMenu()
appSubmenu.addItem(withTitle: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
appItem.submenu = appSubmenu
app.mainMenu = mainMenu

let controller = Controller(model: BMPGlitchModel(data: data), inputPath: inputPath)
let window = controller.buildWindow()
window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)
app.run()
