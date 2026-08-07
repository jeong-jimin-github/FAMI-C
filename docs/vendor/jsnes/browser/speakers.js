// AudioWorklet processor code, inlined as a string so it can be loaded via
// Blob URL without bundler-specific imports (e.g. ?raw). This avoids
// requiring webpack/Vite to import the module source.
//
// The processor receives stereo samples from the main thread via MessagePort
// and buffers them in a circular Float32Array for playback in process().
const workletCode = `
class NESAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    // Circular buffer sized to hold ~170ms of audio at 48kHz (8192 samples).
    this.capacity = 8192;
    this.bufferL = new Float32Array(this.capacity);
    this.bufferR = new Float32Array(this.capacity);
    this.readPos = 0;
    this.writePos = 0;
    this.count = 0;

    this.port.onmessage = (e) => {
      if (e.data.type === "samples") {
        const left = e.data.left;
        const right = e.data.right;
        const len = left.length;

        // If adding these samples would overflow, drop oldest to make room
        if (this.count + len > this.capacity) {
          const drop = this.count + len - this.capacity;
          this.readPos = (this.readPos + drop) % this.capacity;
          this.count -= drop;
        }

        for (let i = 0; i < len; i++) {
          this.bufferL[this.writePos] = left[i];
          this.bufferR[this.writePos] = right[i];
          this.writePos = (this.writePos + 1) % this.capacity;
        }
        this.count += len;
      }
    };
  }

  process(inputs, outputs) {
    const output = outputs[0];
    if (!output || output.length < 2) return true;

    const outL = output[0];
    const outR = output[1];
    const size = outL.length;

    if (this.count < size) {
      for (let i = 0; i < this.count; i++) {
        outL[i] = this.bufferL[this.readPos];
        outR[i] = this.bufferR[this.readPos];
        this.readPos = (this.readPos + 1) % this.capacity;
      }
      for (let i = this.count; i < size; i++) {
        outL[i] = 0;
        outR[i] = 0;
      }
      this.count = 0;
      this.port.postMessage({ type: "underrun" });
    } else {
      for (let i = 0; i < size; i++) {
        outL[i] = this.bufferL[this.readPos];
        outR[i] = this.bufferR[this.readPos];
        this.readPos = (this.readPos + 1) % this.capacity;
      }
      this.count -= size;
    }

    return true;
  }
}

registerProcessor("nes-audio-processor", NESAudioProcessor);
`;

// How many samples to batch before posting to the worklet. Posting every
// single sample individually would be too much MessagePort overhead.
// 128 matches the AudioWorklet render quantum size.
const BATCH_SIZE = 128;

export default class Speakers {
  constructor({ onBufferUnderrun }) {
    this.onBufferUnderrun = onBufferUnderrun;
    this.audioCtx = null;
    this.node = null;
    this.batchL = new Float32Array(BATCH_SIZE);
    this.batchR = new Float32Array(BATCH_SIZE);
    this.batchPos = 0;
    this.legacyBufferL = new Float32Array(8192);
    this.legacyBufferR = new Float32Array(8192);
    this.legacyReadPos = 0;
    this.legacyWritePos = 0;
    this.legacyCount = 0;
    this.usingLegacyOutput = false;
  }

  getSampleRate() {
    if (this.audioCtx) {
      return this.audioCtx.sampleRate;
    }
    return 44100;
  }

  // start() is async because audioWorklet.addModule() returns a promise.
  // Callers may fire-and-forget — the node will be null until the worklet
  // loads, and writeSample() silently drops samples during that brief window.
  async start() {
    if (!window.AudioContext) {
      return;
    }
    this.audioCtx = new window.AudioContext();

    // Register before awaiting worklet setup. On mobile the first tap can
    // otherwise happen while addModule() is pending and be lost.
    if (this.audioCtx.state === "suspended") {
      this._resumeOnInteraction = () => this.resume();
      document.addEventListener("keydown", this._resumeOnInteraction);
      document.addEventListener("pointerdown", this._resumeOnInteraction);
      document.addEventListener("touchstart", this._resumeOnInteraction, {
        passive: true,
      });
    }
    this.resume();

    try {
      if (!this.audioCtx.audioWorklet || !window.AudioWorkletNode) {
        throw new Error("AudioWorklet unavailable");
      }
      const blob = new Blob([workletCode], { type: "application/javascript" });
      const workletUrl = URL.createObjectURL(blob);
      try {
        await this.audioCtx.audioWorklet.addModule(workletUrl);
      } finally {
        URL.revokeObjectURL(workletUrl);
      }

      this.node = new AudioWorkletNode(this.audioCtx, "nes-audio-processor", {
        outputChannelCount: [2],
      });

      this.node.port.onmessage = (e) => {
        if (e.data.type === "underrun" && this.onBufferUnderrun) {
          this.onBufferUnderrun();
        }
      };
    } catch (error) {
      // AudioWorklet is unavailable on non-HTTPS LAN addresses in several
      // mobile browsers. ScriptProcessor remains usable there.
      this._startLegacyOutput();
    }

    this.node.connect(this.audioCtx.destination);

    // Chrome and other browsers require a user gesture before AudioContext can
    // start. If suspended, resume on the first user interaction.
    // See https://github.com/bfirsh/jsnes/issues/368
    this.resume();
  }

  _startLegacyOutput() {
    this.usingLegacyOutput = true;
    this.node = this.audioCtx.createScriptProcessor(2048, 0, 2);
    this.node.onaudioprocess = (event) => {
      const left = event.outputBuffer.getChannelData(0);
      const right = event.outputBuffer.getChannelData(1);
      const available = Math.min(left.length, this.legacyCount);
      for (let i = 0; i < available; i++) {
        left[i] = this.legacyBufferL[this.legacyReadPos];
        right[i] = this.legacyBufferR[this.legacyReadPos];
        this.legacyReadPos = (this.legacyReadPos + 1) % this.legacyBufferL.length;
      }
      for (let i = available; i < left.length; i++) {
        left[i] = 0;
        right[i] = 0;
      }
      this.legacyCount -= available;
      if (available < left.length && this.onBufferUnderrun) {
        this.onBufferUnderrun();
      }
    };
  }

  resume() {
    if (!this.audioCtx || this.audioCtx.state === "running") return;
    this.audioCtx.resume().then(() => this._removeResumeListeners()).catch(() => {});
  }

  _removeResumeListeners() {
    if (this._resumeOnInteraction) {
      document.removeEventListener("keydown", this._resumeOnInteraction);
      document.removeEventListener("pointerdown", this._resumeOnInteraction);
      document.removeEventListener("touchstart", this._resumeOnInteraction);
      this._resumeOnInteraction = null;
    }
  }

  stop() {
    this._removeResumeListeners();
    if (this.node) {
      this.node.onaudioprocess = null;
      this.node.disconnect(this.audioCtx.destination);
      this.node = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close().catch((e) => console.error(e));
      this.audioCtx = null;
    }
    this.batchPos = 0;
    this.legacyReadPos = 0;
    this.legacyWritePos = 0;
    this.legacyCount = 0;
    this.usingLegacyOutput = false;
  }

  writeSample = (left, right) => {
    if (!this.node) return;

    if (this.usingLegacyOutput) {
      if (this.legacyCount === this.legacyBufferL.length) {
        this.legacyReadPos =
          (this.legacyReadPos + 1) % this.legacyBufferL.length;
        this.legacyCount--;
      }
      this.legacyBufferL[this.legacyWritePos] = left;
      this.legacyBufferR[this.legacyWritePos] = right;
      this.legacyWritePos =
        (this.legacyWritePos + 1) % this.legacyBufferL.length;
      this.legacyCount++;
      return;
    }

    this.batchL[this.batchPos] = left;
    this.batchR[this.batchPos] = right;
    this.batchPos++;

    if (this.batchPos >= BATCH_SIZE) {
      this.node.port.postMessage({
        type: "samples",
        left: this.batchL.slice(),
        right: this.batchR.slice(),
      });
      this.batchPos = 0;
    }
  };

  // Flush any remaining batched samples to the worklet. Called after each
  // frame to ensure partial batches are sent promptly.
  flush() {
    if (this.usingLegacyOutput) return;
    if (this.batchPos > 0 && this.node) {
      this.node.port.postMessage({
        type: "samples",
        left: this.batchL.slice(0, this.batchPos),
        right: this.batchR.slice(0, this.batchPos),
      });
      this.batchPos = 0;
    }
  }
}
