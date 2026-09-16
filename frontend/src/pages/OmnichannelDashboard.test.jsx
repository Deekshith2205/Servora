import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import React from "react";
import OmnichannelDashboard from "./OmnichannelDashboard";
import * as client from "../api/client";

// Mock the API client
vi.mock("../api/client", () => ({
  fetchChannels: vi.fn(),
  fetchInbox: vi.fn(),
  fetchAnalyticsSummary: vi.fn(),
}));

describe("OmnichannelDashboard Polling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    client.fetchChannels.mockResolvedValue([]);
    client.fetchAnalyticsSummary.mockResolvedValue({ channel_metrics: [], trend: [] });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("polls fetchInbox for open tickets every 15 seconds", async () => {
    // Initial fetch returns an empty list
    client.fetchInbox.mockResolvedValue([]);
    
    render(<OmnichannelDashboard />);

    // Wait for initial loadData to settle
    await act(async () => {
      await Promise.resolve(); // flush promises
    });

    // Check initial fetch counts
    // fetchInbox should be called twice initially: once for "open" and once for "all"
    expect(client.fetchInbox).toHaveBeenCalledTimes(2);
    expect(client.fetchInbox).toHaveBeenNthCalledWith(1, null, null, "open");
    expect(client.fetchInbox).toHaveBeenNthCalledWith(2);

    // Provide a new ticket for the next polling interval
    const newTicket = {
      id: 1,
      customer: { name: "Polling Customer" },
      channel_key: "whatsapp",
      subject: "New Polled Ticket",
      preview: "Hello",
      status: "open",
      updated_at: new Date().toISOString(),
    };
    client.fetchInbox.mockResolvedValue([newTicket]);

    // Advance timer by 15 seconds
    await act(async () => {
      vi.advanceTimersByTime(15000);
      await Promise.resolve();
    });

    // fetchInbox should have been called a third time with "open"
    expect(client.fetchInbox).toHaveBeenCalledTimes(3);
    expect(client.fetchInbox).toHaveBeenNthCalledWith(3, null, null, "open");

    // The new conversation should now be rendered
    expect(screen.getByText("Polling Customer")).toBeDefined();
    expect(screen.getByText("New Polled Ticket")).toBeDefined();
  });
});
