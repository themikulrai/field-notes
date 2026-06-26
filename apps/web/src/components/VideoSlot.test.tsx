import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VideoSlot } from "./VideoSlot";
import type { VideoSlot as VideoSlotData } from "../lib/types";

function mk(overrides: Partial<VideoSlotData> = {}): VideoSlotData {
  return {
    label: "rollout seed 42",
    duration: "0:12",
    url: "https://example.com/clip.mp4",
    ...overrides,
  };
}

describe("VideoSlot", () => {
  it("renders <video> with controls when url is present", () => {
    const { container } = render(<VideoSlot video={mk()} />);
    const video = container.querySelector("video");
    expect(video).not.toBeNull();
    expect(video!.hasAttribute("controls")).toBe(true);
  });

  it("renders <source> with correct src and type (default mp4)", () => {
    const { container } = render(<VideoSlot video={mk()} />);
    const source = container.querySelector("video > source");
    expect(source).not.toBeNull();
    expect(source!.getAttribute("src")).toBe("https://example.com/clip.mp4");
    expect(source!.getAttribute("type")).toBe("video/mp4");
  });

  it("uses video.mime when provided", () => {
    const { container } = render(
      <VideoSlot video={mk({ mime: "video/webm" })} />,
    );
    const source = container.querySelector("video > source");
    expect(source!.getAttribute("type")).toBe("video/webm");
  });

  it("shows ffmpeg banner after error event fires on the video", () => {
    const { container } = render(<VideoSlot video={mk()} />);
    const video = container.querySelector("video")!;
    fireEvent.error(video);
    const code = container.querySelector("code");
    expect(code).not.toBeNull();
    expect(code!.textContent).toBe(
      "ffmpeg -i in.mp4 -c:v libx264 -pix_fmt yuv420p -movflags +faststart out.mp4",
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows 'no source' placeholder when url is null", () => {
    const { container } = render(<VideoSlot video={mk({ url: null })} />);
    expect(container.querySelector("video")).toBeNull();
    expect(screen.getByTestId("no-source-placeholder")).toBeInTheDocument();
    expect(screen.getByText("no source")).toBeInTheDocument();
  });

  it("shows 'no source' placeholder when url is empty string", () => {
    const { container } = render(<VideoSlot video={mk({ url: "" })} />);
    expect(container.querySelector("video")).toBeNull();
    expect(screen.getByTestId("no-source-placeholder")).toBeInTheDocument();
  });

  it("renders label and duration caption", () => {
    render(<VideoSlot video={mk()} />);
    expect(screen.getByText("rollout seed 42")).toBeInTheDocument();
    expect(screen.getByText("0:12")).toBeInTheDocument();
  });

  it("flags an external (non-/media) url as 'may drop'", () => {
    render(<VideoSlot video={mk({ url: "https://example.com/clip.mp4" })} />);
    expect(screen.getByText(/external — may drop/i)).toBeInTheDocument();
  });

  it("does NOT flag a /media-hosted url", () => {
    render(<VideoSlot video={mk({ url: "/media/lb/clip.mp4" })} />);
    expect(screen.queryByText(/external — may drop/i)).toBeNull();
  });

  it("does NOT flag an absolute herokuapp /media url", () => {
    render(<VideoSlot video={mk({ url: "https://field-notes.herokuapp.com/media/lb/clip.mp4" })} />);
    expect(screen.queryByText(/external — may drop/i)).toBeNull();
  });
});
