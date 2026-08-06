#!/usr/bin/env swift

import Cocoa
import ImageIO

// ---------------------------------------------------------------------------
// glitchlab.swift — interactive JPEG glitch lab.
//
//   swiftc glitchlab.swift -o glitchlab
//   ./glitchlab <image.jpg>
//
// Side-by-side original vs. glitched, with one slider per JPEG region
// (data / quant / huffman / frame / header), a master "count" slider, and an
// adjustable seed. Every control change re-glitches from the pristine original
// (corruption is never cumulative).
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

// MARK: - JPEG segment parser → payload byte ranges per region

func parseJPEG(_ b: [UInt8]) -> [String: [Range<Int>]] {
    var regions: [String: [Range<Int>]] = [
        "header": [], "huffman": [], "quant": [], "frame": [], "data": []
    ]
    guard b.count > 4, b[0] == 0xFF, b[1] == 0xD8 else {
        die("Not a JPEG (missing SOI marker).")
    }

    var i = 2
    while i + 1 < b.count {
        guard b[i] == 0xFF else { i += 1; continue }
        var marker = b[i + 1]
        while marker == 0xFF, i + 2 < b.count { i += 1; marker = b[i + 1] }

        if marker == 0xD8 || marker == 0x01 || (marker >= 0xD0 && marker <= 0xD7) {
            i += 2; continue
        }
        if marker == 0xD9 { break } // EOI

        guard i + 3 < b.count else { break }
        let length = Int(b[i + 2]) << 8 | Int(b[i + 3])
        let dataStart = i + 4
        let segEnd = i + 2 + length
        let payload = dataStart..<min(segEnd, b.count)

        switch marker {
        case 0xE0...0xEF, 0xFE:                          // APPn, COM
            regions["header", default: []].append(payload)
        case 0xC4:                                       // DHT
            regions["huffman", default: []].append(payload)
        case 0xDB:                                       // DQT
            regions["quant", default: []].append(payload)
        case 0xC0...0xC3, 0xC5...0xCB, 0xCD...0xCF:      // SOFn (frame)
            regions["frame", default: []].append(payload)
        case 0xDA:                                       // SOS — entropy data follows
            let scanStart = segEnd
            var j = scanStart
            while j + 1 < b.count {
                if b[j] == 0xFF {
                    let m = b[j + 1]
                    if m == 0x00 || (m >= 0xD0 && m <= 0xD7) { j += 2; continue }
                    break
                }
                j += 1
            }
            regions["data", default: []].append(scanStart..<min(j, b.count))
            i = min(j, b.count)
            continue
        default:
            break
        }
        i = segEnd
    }
    return regions
}

// MARK: - Tolerant image loader

func loadImage(from data: Data) -> NSImage? {
    if let src = CGImageSourceCreateWithData(data as CFData, nil),
       let cg = CGImageSourceCreateImageAtIndex(src, 0,
                    [kCGImageSourceShouldCache: true] as CFDictionary) {
        return NSImage(cgImage: cg, size: NSSize(width: cg.width, height: cg.height))
    }
    return NSImage(data: data)
}

// MARK: - Glitch model

final class GlitchModel {
    let original: [UInt8]
    private(set) var pools: [String: [Int]] = [:]   // candidate byte indices per region

    init(data: Data) {
        original = [UInt8](data)
        let ranges = parseJPEG(original)
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
    let regionOrder = ["data", "quant", "huffman", "frame", "header"]
    let maxCount = 3000

    var weights: [String: Double]
    var count = 300
    var seed: UInt64 = 1
    var lastData: Data

    let originalView = NSImageView()
    let glitchedView = NSImageView()
    var regionValueLabels: [String: NSTextField] = [:]
    var countValueLabel = makeLabel("")
    var seedValueLabel = makeLabel("")
    var seedSlider = NSSlider()
    var statusLabel = makeLabel("")

    init(model: GlitchModel, inputPath: String) {
        self.model = model
        self.inputPath = inputPath
        self.weights = ["data": 0, "quant": 0, "huffman": 0, "frame": 0, "header": 0]
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
            let name = "\(region)"
            controlRows.append(sliderRow(name: name, slider: slider, trailing: valueLabel))
        }

        // Count slider.
        let countSlider = NSSlider(value: Double(count), minValue: 0, maxValue: Double(maxCount),
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
        window.title = "JPEGlab — \((inputPath as NSString).lastPathComponent)"
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
        let row = NSStackView(views: [makeLabel(name, width: 70), slider, trailing])
        row.orientation = .horizontal
        row.spacing = 10
        return row
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
        seed = UInt64.random(in: 0...9999)
        seedSlider.doubleValue = Double(seed)
        recompute()
    }

    @objc private func save() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue =
            (inputPath as NSString).deletingPathExtension.components(separatedBy: "/").last!
            + ".glitch.jpg"
        panel.allowedContentTypes = [.jpeg]
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
guard args.count >= 2 else { die("Usage: glitchlab <image.jpg>") }
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
