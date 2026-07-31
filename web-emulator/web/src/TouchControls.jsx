import React from "react";
import { Controller } from "jsnes";

function TouchButton({ label, button, onPress, onRelease, className = "" }) {
  const press = (event) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    onPress(button);
  };
  const release = (event) => {
    event.preventDefault();
    onRelease(button);
  };

  return (
    <button
      type="button"
      aria-label={label}
      className={`select-none touch-none rounded-full border-2 border-white/70 bg-gray-800/90 text-white active:bg-white active:text-black ${className}`}
      onPointerDown={press}
      onPointerUp={release}
      onPointerCancel={release}
      onContextMenu={(event) => event.preventDefault()}
    >
      {label}
    </button>
  );
}

export default function TouchControls({ onPress, onRelease }) {
  return (
    <div className="touch-controls fixed inset-x-0 bottom-0 z-20 h-[210px] bg-black/85 px-4 py-3 md:hidden">
      <div className="relative mx-auto flex h-full max-w-xl items-center justify-between gap-2">
        <div className="grid h-[124px] w-[124px] shrink-0 grid-cols-3 grid-rows-3 gap-1">
          <TouchButton label="▲" button={Controller.BUTTON_UP} onPress={onPress} onRelease={onRelease} className="col-start-2" />
          <TouchButton label="◀" button={Controller.BUTTON_LEFT} onPress={onPress} onRelease={onRelease} className="row-start-2" />
          <div className="row-start-2 rounded bg-gray-700" />
          <TouchButton label="▶" button={Controller.BUTTON_RIGHT} onPress={onPress} onRelease={onRelease} className="row-start-2" />
          <TouchButton label="▼" button={Controller.BUTTON_DOWN} onPress={onPress} onRelease={onRelease} className="col-start-2 row-start-3" />
        </div>

        <div className="absolute bottom-0 left-1/2 flex -translate-x-1/2 gap-2">
          <TouchButton label="SELECT" button={Controller.BUTTON_SELECT} onPress={onPress} onRelease={onRelease} className="h-9 w-16 rounded-xl text-[10px]" />
          <TouchButton label="START" button={Controller.BUTTON_START} onPress={onPress} onRelease={onRelease} className="h-9 w-16 rounded-xl text-[10px]" />
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <TouchButton label="B" button={Controller.BUTTON_B} onPress={onPress} onRelease={onRelease} className="mt-10 h-14 w-14 text-xl" />
          <TouchButton label="A" button={Controller.BUTTON_A} onPress={onPress} onRelease={onRelease} className="mb-10 h-14 w-14 text-xl" />
        </div>
      </div>
    </div>
  );
}
