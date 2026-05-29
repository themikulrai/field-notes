import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

function Boom(): never {
  throw new Error("kaboom");
}

describe("ErrorBoundary", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders children when nothing throws", () => {
    render(
      <ErrorBoundary>
        <div>all good</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("all good")).toBeInTheDocument();
  });

  it("catches a child render throw and shows a recoverable panel instead of a blank page", () => {
    // React logs the caught error; silence it to keep test output clean.
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/Something broke/i)).toBeInTheDocument();
    expect(screen.getByText("kaboom")).toBeInTheDocument();
    // recovery affordances are present
    expect(screen.getByText("try again")).toBeInTheDocument();
    expect(screen.getByText("reload")).toBeInTheDocument();
  });

  it("'try again' clears the error and re-renders children", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    let shouldThrow = true;
    function Maybe() {
      if (shouldThrow) throw new Error("once");
      return <div>recovered</div>;
    }
    render(
      <ErrorBoundary>
        <Maybe />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/Something broke/i)).toBeInTheDocument();
    shouldThrow = false;
    fireEvent.click(screen.getByText("try again"));
    expect(screen.getByText("recovered")).toBeInTheDocument();
  });
});
