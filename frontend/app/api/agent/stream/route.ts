export const dynamic = "force-dynamic";

const encoder = new TextEncoder();

function sendEvent(controller: ReadableStreamDefaultController, event: string, payload: unknown) {
  controller.enqueue(encoder.encode(`event: ${event}\n`));
  controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
}

function buildReply(prompt: string, context: string) {
  const normalized = prompt.toLowerCase();

  if (context === "general") {
    if (normalized.includes("route") || normalized.includes("delayed")) {
      return "Across the network, delayed trips are concentrated on BLR-17, BLR-22, and BLR-08. The first areas to review are morning capacity, route allocation, and recurring late arrivals by vendor.";
    }

    if (normalized.includes("ota") || normalized.includes("overview") || normalized.includes("performance")) {
      return "The network view should focus on OTA trend, delayed-trip concentration, vendor performance, and available vehicle capacity. Current attention should remain on morning operations, where route pressure is most likely to affect SLA.";
    }

    return "I can help with general mobility operations across OTA, routes, delays, capacity, vendors, and recovery actions. Ask about a network trend or a specific operating area to narrow the analysis.";
  }

  if (normalized.includes("route") || normalized.includes("top routes") || normalized.includes("delayed trips")) {
    return "The top delayed routes are BLR-17, BLR-22, and BLR-08. BLR-17 is the biggest pressure point, with delays clustering before 9 AM and a higher share of late arrivals than the rest of the network.";
  }

  if (normalized.includes("vendor") || normalized.includes("alpha")) {
    return "Vendor Alpha is the main driver of the SLA breach. OTA has fallen to 71% this week, and the increase in late trips is concentrated on the early-morning shifts where route capacity is thin.";
  }

  if (normalized.includes("reason") || normalized.includes("why")) {
    return "The most likely cause is route allocation strain: the morning trips are overloaded, vehicle coverage is not keeping up with demand, and vendor delays are compounding on the most critical route segments.";
  }

  if (normalized.includes("action") || normalized.includes("improve")) {
    return "Recommended actions are to increase vehicle coverage for BLR-17 and BLR-22, review the Vendor Alpha allocation plan, and recalibrate route assignment before the next peak period so OTA recovers above the 90% SLA.";
  }

  return "The current signal shows the main issue is a combination of route-level pressure and Vendor Alpha performance during the morning window. I recommend checking allocation on BLR-17 and confirming a recovery plan before the next shift starts.";
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const prompt = searchParams.get("message") ?? "How did the OTA drop for Vendor Alpha this week?";
  const context = searchParams.get("context") ?? "vendor-alpha";
  const reply = buildReply(prompt, context);

  const stream = new ReadableStream({
    start(controller) {
      const timers: ReturnType<typeof setTimeout>[] = [];
      let index = 0;

      sendEvent(controller, "status", { connected: true, service: "mobility-agent" });

      const tick = () => {
        const chunk = reply.slice(0, index + 1);
        sendEvent(controller, "message", {
          role: "assistant",
          text: chunk,
          sequence: 1,
          timestamp: new Date().toISOString(),
        });

        index += 1;

        if (index >= reply.length) {
          sendEvent(controller, "done", { status: "complete", prompt });
          timers.push(setTimeout(() => controller.close(), 250));
          return;
        }

        timers.push(setTimeout(tick, 18));
      };

      timers.push(setTimeout(tick, 200));

      const close = () => {
        for (const timer of timers) clearTimeout(timer);
        controller.close();
      };

      (controller as ReadableStreamDefaultController & { closeStream?: () => void }).closeStream = close;
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
