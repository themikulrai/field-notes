import { useState } from "react";
import type { VideoSlot as VideoSlotData } from "../lib/types";

const FFMPEG_CMD =
  "ffmpeg -i in.mp4 -c:v libx264 -pix_fmt yuv420p -movflags +faststart out.mp4";

// /media is baked into the Heroku image and data: URIs are inline — both stable.
// Anything else is an external host whose connection can drop, so we flag it.
function isStableVideoUrl(url: string): boolean {
  return url.startsWith("/media") || url.includes("/media/") || url.startsWith("data:");
}

export function VideoSlot({ video }: { video: VideoSlotData }) {
  const [error, setError] = useState(false);
  const hasSource = !!(video.url && video.url.length > 0);
  const external = hasSource && !isStableVideoUrl(video.url as string);

  return (
    <div className="video-slot">
      {hasSource ? (
        <video
          controls
          preload="metadata"
          playsInline
          onError={() => setError(true)}
          style={{ width: "100%", height: "auto", display: "block" }}
        >
          <source src={video.url as string} type={video.mime || "video/mp4"} />
        </video>
      ) : (
        <div className="video-placeholder" data-testid="no-source-placeholder">
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
          <span className="mono dim">no source</span>
        </div>
      )}
      {error && (
        <div className="video-error-banner" role="alert">
          <span className="mono dim">
            Browser couldn't decode this video. Transcode with:
          </span>
          <code>{FFMPEG_CMD}</code>
        </div>
      )}
      <div className="video-meta">
        <span className="mono">{video.label}</span>
        <span className="mono dim">{video.duration}</span>
        {external && (
          <span className="video-external mono" title={video.url as string}>
            ⚠ external — may drop
          </span>
        )}
      </div>
    </div>
  );
}
