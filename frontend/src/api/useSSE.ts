import { useEffect, useReducer, useRef, useCallback } from 'react'
import i18n from '../i18n'
import type { PipelineEvent } from '../types/research'
import { getApiHeaders, getStreamUrl } from "./client";

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 15000;
const MAX_EVENT_HISTORY = 200;
const STREAM_EVENT_TYPES = new Set([
	"intent_started",
	"intent_parsed",
	"source_started",
	"source_completed",
	"source_failed",
	"extraction_started",
	"extraction_completed",
	"aggregation_started",
	"aggregation_completed",
	"report_ready",
	"cancelled",
	"error",
]);

interface SSEState {
	events: PipelineEvent[];
	isComplete: boolean;
	isReconnecting: boolean;
	error: string | null;
	cancelled: string | null;
}

type SSEAction =
	| { type: "reset" }
	| { type: "event"; event: PipelineEvent }
	| { type: "complete" }
	| { type: "cancelled"; message: string }
	| { type: "error"; message: string }
	| { type: "reconnecting" };

function eventKey(event: PipelineEvent): string {
	return `${event.type}|${event.stage}|${event.timestamp}`;
}

function sseReducer(state: SSEState, action: SSEAction): SSEState {
	switch (action.type) {
		case "reset":
			return { events: [], isComplete: false, isReconnecting: false, error: null, cancelled: null };
		case "event":
			if (state.events.some((existing) => eventKey(existing) === eventKey(action.event))) {
				return { ...state, isReconnecting: false };
			}
			return {
				...state,
				events: [...state.events, action.event].slice(-MAX_EVENT_HISTORY),
				isReconnecting: false,
			};
		case "complete":
			return { ...state, isComplete: true, isReconnecting: false };
		case "cancelled":
			return { ...state, cancelled: action.message, isComplete: true, isReconnecting: false };
		case "error":
			return { ...state, error: action.message, cancelled: null, isComplete: true, isReconnecting: false };
		case "reconnecting":
			return { ...state, isReconnecting: true };
	}
}

export interface UseSSEResult {
	events: PipelineEvent[];
	isComplete: boolean;
	isReconnecting: boolean;
	error: string | null;
	cancelled: string | null;
	retry: () => void;
}

function clearReconnectTimer(timerRef: React.RefObject<ReturnType<typeof setTimeout> | null>): void {
	if (timerRef.current) {
		clearTimeout(timerRef.current);
		timerRef.current = null;
	}
}

/**
 * Parse a single SSE chunk buffer into individual events.
 * Returns emitted { eventType, data } pairs.
 */
function* parseSseChunk(buffer: string): Generator<{ eventType: string; data: string }> {
	const blocks = buffer.split(/\n\n/);
	for (const block of blocks) {
		if (!block.trim()) continue;
		let eventType = "message";
		let data = "";
		for (const line of block.split("\n")) {
			if (line.startsWith("event:")) {
				eventType = line.slice(6).trim();
			} else if (line.startsWith("data:")) {
				data = line.slice(5).trim();
			}
		}
		if (data) yield { eventType, data };
	}
}

export function useSSE(reportId: string | null): UseSSEResult {
	const [state, dispatch] = useReducer(sseReducer, {
		events: [],
		isComplete: false,
		isReconnecting: false,
		error: null,
		cancelled: null,
	});
	const abortRef = useRef<AbortController | null>(null);
	const attemptRef = useRef(0);
	const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const isCompleteRef = useRef(false);
	const connectRef = useRef<((id: string) => void) | null>(null);

	useEffect(() => {
		isCompleteRef.current = state.isComplete;
	}, [state.isComplete]);

	const cleanupConnection = useCallback(() => {
		if (abortRef.current) {
			abortRef.current.abort();
			abortRef.current = null;
		}
	}, []);

	const connect = useCallback(
		(id: string) => {
			if (isCompleteRef.current) return;
			cleanupConnection();
			clearReconnectTimer(reconnectTimerRef);

			const controller = new AbortController();
			abortRef.current = controller;

			const url = getStreamUrl(id);

			(async () => {
				try {
					const res = await fetch(url, {
						headers: { ...getApiHeaders(), Accept: "text/event-stream" },
						signal: controller.signal,
					});

					if (!res.ok || !res.body) {
						throw new Error(`SSE connection failed: ${res.status}`);
					}

					const reader = res.body.getReader();
					const decoder = new TextDecoder();
					let buffer = "";

					while (true) {
						const { done, value } = await reader.read();
						if (done) break;

						buffer += decoder.decode(value, { stream: true });

						// Process complete SSE blocks (separated by double newline)
						const lastDoubleNewline = buffer.lastIndexOf("\n\n");
						if (lastDoubleNewline === -1) continue;

						const toProcess = buffer.slice(0, lastDoubleNewline + 2);
						buffer = buffer.slice(lastDoubleNewline + 2);

						for (const { eventType, data } of parseSseChunk(toProcess)) {
							if (!STREAM_EVENT_TYPES.has(eventType)) continue;
							try {
								const event: PipelineEvent = JSON.parse(data);
								attemptRef.current = 0;
								dispatch({ type: "event", event });
								if (event.type === "report_ready") {
									dispatch({ type: "complete" });
									return;
								}
								if (event.type === "error") {
									dispatch({ type: "error", message: event.message });
									return;
								}
								if (event.type === "cancelled") {
									dispatch({ type: "cancelled", message: event.message });
									return;
								}
							} catch {
								// ignore parse errors (e.g. ping events with no JSON)
							}
						}
					}

					// Stream ended without a terminal event — trigger reconnect
					if (!isCompleteRef.current) throw new Error("Stream closed unexpectedly");
				} catch (err) {
					if ((err as Error).name === "AbortError") return; // intentional abort

					if (isCompleteRef.current) return;

					attemptRef.current += 1;
					if (attemptRef.current > MAX_RECONNECT_ATTEMPTS) {
						dispatch({ type: "error", message: i18n.t("report.error.connectionLost") });
						return;
					}

					dispatch({ type: "reconnecting" });
					const delay = Math.min(BASE_DELAY_MS * Math.pow(2, attemptRef.current - 1), MAX_DELAY_MS);
					reconnectTimerRef.current = setTimeout(() => connectRef.current?.(id), delay);
				}
			})();
		},
		[cleanupConnection],
	);

	useEffect(() => {
		connectRef.current = connect;
	}, [connect]);

	const retry = useCallback(() => {
		if (!reportId) return;
		dispatch({ type: "reset" });
		attemptRef.current = 0;
		isCompleteRef.current = false;
		connect(reportId);
	}, [connect, reportId]);

	useEffect(() => {
		if (!reportId) return;

		dispatch({ type: "reset" });
		attemptRef.current = 0;
		isCompleteRef.current = false;
		connect(reportId);

		return () => {
			cleanupConnection();
			clearReconnectTimer(reconnectTimerRef);
		};
	}, [cleanupConnection, connect, reportId]);

	return { ...state, retry };
}
