import type { VideoSlot as VideoSlotData } from "../lib/types";

export function VideoSlot({ video }: { video: VideoSlotData }) {
  return (
    <div className="video-slot">
      <svg viewBox="0 0 100 56" preserveAspectRatio="none" className="video-bg">
        <defs>
          <pattern
            id="stripes"
            patternUnits="userSpaceOnUse"
            width="6"
            height="6"
            patternTransform="rotate(35)"
          >
            <rect width="6" height="6" fill="var(--paper-2)" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--rule)" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100" height="56" fill="url(#stripes)" />
      </svg>
      <div className="video-play">
        <svg viewBox="0 0 24 24" width="22" height="22">
          <path d="M8 5v14l11-7z" fill="currentColor" />
        </svg>
      </div>
      <div className="video-meta">
        <span className="mono">{video.label}</span>
        <span className="mono dim">{video.duration}</span>
      </div>
    </div>
  );
}
