#!/usr/bin/env swift

import Cocoa
import ImageIO

// ---------------------------------------------------------------------------
// giflab.swift — interactive GIF glitch lab.
//
//   swiftc giflab.swift -o giflab
//   ./giflab <image.gif>
//
// Side-by-side original vs. glitched, with one slider per GIF region
// (global color table / image data / graphic control extension), a master
// "count" slider, and an adjustable seed. Every control change re-glitches
// from the pristine original (corruption is never cumulative).
//
// Per region the number of mutated bytes is round(count * weight), where weight
// is that region's slider (0…1).
// ---------------------------------------------------------------------------

// MARK: - Seedable RNG (SplitMix64)

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

// MARK: - GIF segment parser → payload byte ranges per region

func parseGIF(_ b: [UInt8]) -> [String: [Range<Int>]] {
    var regions: [String: [Range<Int>]] = ["global": [], "local": [], "image": [], "speed": []]

    guard b.count >= 13 else { return regions }
    let signature = String(bytes: b[0..<6], encoding: .ascii)
    guard signature == "GIF87a" || signature == "GIF89a" else { return regions }

    let gctStart = 13
    let packedFields = b[10]
    let hasGlobalColorTable = (packedFields & 0x80) != 0
    let gctSizeBits = Int(packedFields & 0x07)
    let gctByteCount = hasGlobalColorTable ? 3 * (1 << (gctSizeBits + 1)) : 0
    let gctEnd = gctStart + gctByteCount
    if gctByteCount > 0, gctEnd <= b.count {
        regions["global", default: []].append(gctStart..<gctEnd)
    }

    var i = gctEnd
    while i < b.count {
        switch b[i] {
        case 0x21:
            if i + 1 < b.count, b[i + 1] == 0xF9 {
                let speedStart = i + 4
                let speedEnd = i + 6
                if speedStart < speedEnd, speedEnd <= b.count {
                    regions["speed", default: []].append(speedStart..<speedEnd)
                }
                i += 8
            } else {
                var j = i + 2
                while j < b.count {
                    let size = Int(b[j])
                    if size == 0 {
                        j += 1
                        break
                    }
                    j += size + 1
                }
                i = min(j, b.count)
            }

        case 0x2C:
            guard i + 9 < b.count else { break }
            let packed = b[i + 9]
            let hasLocalColorTable = (packed & 0x80) != 0
            let localTableBits = Int(packed & 0x07)
            let localTableByteCount = hasLocalColorTable ? 3 * (1 << (localTableBits + 1)) : 0
            if hasLocalColorTable {
                let localTableStart = i + 10
                let localTableEnd = localTableStart + localTableByteCount
                if localTableStart < localTableEnd, localTableEnd <= b.count {
                    regions["local", default: []].append(localTableStart..<localTableEnd)
                }
            }

            let lzwMinCodeSizeIndex = i + 10 + localTableByteCount
            guard lzwMinCodeSizeIndex < b.count else { break }

            var j = lzwMinCodeSizeIndex + 1
            while j < b.count {
                let size = Int(b[j])
                if size == 0 {
                    j += 1
                    break
                }
                let payloadStart = j + 1
                let payloadEnd = payloadStart + size
                if payloadStart < payloadEnd, payloadEnd <= b.count {
                    regions["image", default: []].append(payloadStart..<payloadEnd)
                }
                j = payloadEnd
            }
            i = min(j, b.count)

        case 0x3B:
            return regions

        default:
            i += 1
        }
    }
    return regions
}

// MARK: - Tolerant image loader

func loadImage(from data: Data) -> NSImage? {
    if let image = NSImage(data: data) { return image }
    if let src = CGImageSourceCreateWithData(data as CFData, nil),
       let cg = CGImageSourceCreateImageAtIndex(src, 0,
                    [kCGImageSourceShouldCache: true] as CFDictionary) {
        return NSImage(cgImage: cg, size: NSSize(width: cg.width, height: cg.height))
    }
    return nil
}

// MARK: - Glitch model

final class GlitchModel {
    let original: [UInt8]
    private(set) var pools: [String: [Int]] = [:]   // candidate byte indices per region

    init(data: Data) {
        original = [UInt8](data)
        let ranges = parseGIF(original)
        for (key, rs) in ranges {
            var idxs: [Int] = []
            for r in rs { idxs.append(contentsOf: r) }
            pools[key] = idxs
        }
    }

    func poolSize(_ region: String) -> Int { pools[region]?.count ?? 0 }

    /// Re-glitch from scratch. `count` is the master byte budget; each region
    /// mutates round(count * weight) bytes. Deterministic for a given (weights,
    /// count, seed). Returns the bytes and the total number mutated.
    func render(order: [String], weights: [String: Double], count: Int, seed: UInt64)
        -> (data: Data, changed: Int) {
        var bytes = original
        var rng = SplitMix64(seed: seed)
        var changed = 0
        for region in order {
            guard let pool = pools[region], !pool.isEmpty else { continue }
            let w = weights[region] ?? 0
            let n = Int((Double(count) * w).rounded())
            if n <= 0 { continue }
            for _ in 0..<n {
                let idx = pool[Int(rng.next() % UInt64(pool.count))]
                var nb = UInt8(rng.next() & 0xFF)
                if nb == 0xFF { nb = 0xFE } // avoid forging markers/truncation
                bytes[idx] = nb
                changed += 1
            }
        }
        return (Data(bytes), changed)
    }
}

// MARK: - UI helpers

func makeLabel(_ text: String, width: CGFloat? = nil, bold: Bool = false) -> NSTextField {
    let f = NSTextField(labelWithString: text)
    f.font = bold ? .boldSystemFont(ofSize: 12) : .systemFont(ofSize: 12)
    if let w = width {
        f.translatesAutoresizingMaskIntoConstraints = false
        f.widthAnchor.constraint(equalToConstant: w).isActive = true
    }
    return f
}

// MARK: - Controller

final class Controller: NSObject {
    let model: GlitchModel
    let inputPath: String
    let regionOrder = ["global", "local", "image"]
    let maxCount = 10000

    var weights: [String: Double]
    var count = 100
    var seed: UInt64 = 1
    var lastData: Data

    let originalView = NSImageView()
    let glitchedView = NSImageView()
    var regionValueLabels: [String: NSTextField] = [:]
    var regionSliders: [String: NSSlider] = [:]
    var countValueLabel = makeLabel("")
    var seedValueLabel = makeLabel("")
    var countSlider = NSSlider()
    var seedSlider = NSSlider()
    var statusLabel = makeLabel("")

    init(model: GlitchModel, inputPath: String) {
        self.model = model
        self.inputPath = inputPath
        self.weights = ["global": 0, "local": 0, "image": 0]
        self.lastData = Data(model.original)
        super.init()
    }

    // MARK: View

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

        // Control rows.
        var controlRows: [NSView] = []
        for (i, region) in regionOrder.enumerated() {
            let slider = NSSlider(value: 0, minValue: 0, maxValue: 1,
                                  target: self, action: #selector(regionChanged(_:)))
            slider.tag = i
            let valueLabel = makeLabel("", width: 150)
            regionValueLabels[region] = valueLabel
            regionSliders[region] = slider
            let name = regionDisplayName(for: region)
            controlRows.append(sliderRow(name: name, slider: slider, trailing: valueLabel))
        }

        // Count slider.
        countSlider = NSSlider(value: Double(count), minValue: 0, maxValue: Double(maxCount),
                               target: self, action: #selector(countChanged(_:)))
        controlRows.append(sliderRow(name: "count", slider: countSlider, trailing: countValueLabel))

        // Seed slider + randomize.
        seedSlider = NSSlider(value: Double(seed), minValue: 0, maxValue: 9999,
                              target: self, action: #selector(seedChanged(_:)))
        let randomizeButton = NSButton(title: "Random", target: self,
                                       action: #selector(randomizeSeed))
        let seedTrailing = NSStackView(views: [seedValueLabel, randomizeButton])
        seedTrailing.orientation = .horizontal
        seedTrailing.spacing = 8
        seedValueLabel.translatesAutoresizingMaskIntoConstraints = false
        seedValueLabel.widthAnchor.constraint(equalToConstant: 70).isActive = true
        controlRows.append(sliderRow(name: "seed", slider: seedSlider, trailing: seedTrailing))

        // Save button + status.
        let saveButton = NSButton(title: "Save glitched…", target: self,
                                  action: #selector(save))
        let bottomRow = NSStackView(views: [saveButton, statusLabel])
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
        window.title = "GIFlab — \((inputPath as NSString).lastPathComponent)"
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
        let row = NSStackView(views: [makeLabel(name, width: 140), slider, trailing])
        row.orientation = .horizontal
        row.spacing = 10
        return row
    }

    private func regionDisplayName(for region: String) -> String {
        switch region {
        case "global": return "global color table"
        case "local": return "frame color table"
        case "image": return "image data"
        case "speed": return "frame speed"
        default: return region
        }
    }

    // MARK: Actions

    @objc private func regionChanged(_ sender: NSSlider) {
        let region = regionOrder[sender.tag]
        weights[region] = sender.doubleValue
        recompute()
    }

    @objc private func countChanged(_ sender: NSSlider) {
        count = Int(sender.doubleValue.rounded())
        recompute()
    }

    @objc private func seedChanged(_ sender: NSSlider) {
        seed = UInt64(sender.doubleValue.rounded())
        recompute()
    }

    @objc private func randomizeSeed() {
        for region in regionOrder {
            let randomWeight = Double.random(in: 0...1)
            weights[region] = randomWeight
            regionSliders[region]?.doubleValue = randomWeight
        }
        count = Int.random(in: 0...maxCount)
        countSlider.doubleValue = Double(count)
        seed = UInt64.random(in: 0...9999)
        seedSlider.doubleValue = Double(seed)
        recompute()
    }

    @objc private func save() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue =
            (inputPath as NSString).deletingPathExtension.components(separatedBy: "/").last!
            + ".glitch.gif"
        panel.allowedContentTypes = [.gif]
        if panel.runModal() == .OK, let url = panel.url {
            try? lastData.write(to: url)
            statusLabel.stringValue = "Saved \(url.lastPathComponent)"
        }
    }

    // MARK: Render

    private func recompute() {
        let result = model.render(order: regionOrder, weights: weights,
                                  count: count, seed: seed)
        lastData = result.data
        let image = loadImage(from: result.data)
        glitchedView.image = image

        for region in regionOrder {
            let n = Int((Double(count) * (weights[region] ?? 0)).rounded())
            regionValueLabels[region]?.stringValue = "\(n) / \(model.poolSize(region)) B"
        }
        countValueLabel.stringValue = "\(count)"
        seedValueLabel.stringValue = "\(seed)"
        statusLabel.stringValue = image == nil
            ? "decode FAILED — region too corrupted (\(result.changed) B)"
            : "mutated \(result.changed) B · \(lastData.count) B total"
    }
}

// MARK: - Bootstrap

let args = CommandLine.arguments
guard args.count >= 2 else { die("Usage: giflab <image.gif>") }
let inputPath = args[1]
guard let data = FileManager.default.contents(atPath: inputPath) else {
    die("Could not read file: \(inputPath)")
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)

// Minimal menu so Cmd-Q works.
let mainMenu = NSMenu()
let appItem = NSMenuItem()
mainMenu.addItem(appItem)
let appSubmenu = NSMenu()
appSubmenu.addItem(withTitle: "Quit", action: #selector(NSApplication.terminate(_:)),
                   keyEquivalent: "q")
appItem.submenu = appSubmenu
app.mainMenu = mainMenu

let controller = Controller(model: GlitchModel(data: data), inputPath: inputPath)
let window = controller.buildWindow()
window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)
app.run()
