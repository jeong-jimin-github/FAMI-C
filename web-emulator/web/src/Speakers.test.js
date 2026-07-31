import { afterEach, expect, test, vi } from "vitest";
import Speakers from "../../src/browser/speakers";

afterEach(() => {
  delete window.AudioContext;
  delete window.AudioWorkletNode;
});

test("falls back to audio output that works without AudioWorklet", async () => {
  const node = { connect: vi.fn(), disconnect: vi.fn(), onaudioprocess: null };
  class MockAudioContext {
    state = "running";
    sampleRate = 48000;
    destination = {};
    createScriptProcessor() {
      return node;
    }
    close() {
      return Promise.resolve();
    }
  }
  window.AudioContext = MockAudioContext;

  const speakers = new Speakers({ onBufferUnderrun: vi.fn() });
  await speakers.start();
  expect(speakers.usingLegacyOutput).toBe(true);

  speakers.writeSample(0.25, -0.25);
  const channels = [new Float32Array(4), new Float32Array(4)];
  node.onaudioprocess({
    outputBuffer: { getChannelData: (channel) => channels[channel] },
  });
  expect(channels[0][0]).toBe(0.25);
  expect(channels[1][0]).toBe(-0.25);
  speakers.stop();
});
