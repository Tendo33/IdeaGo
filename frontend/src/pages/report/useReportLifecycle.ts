<<<<<<< HEAD
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from "react-i18next";
import type { NavigateFunction } from "react-router-dom";
import { cancelAnalysis, getReportWithStatus, startAnalysis } from "../../api/client";
import { useSSE } from "../../api/useSSE";
import type { ResearchReport } from "../../types/research";
=======
import { useCallback, useEffect, useRef, useState } from 'react'
import type { NavigateFunction } from 'react-router-dom'
import { cancelAnalysis, getReportWithStatus, startAnalysis } from '../../api/client'
import { useSSE } from '../../api/useSSE'
import type { ResearchReport } from '../../types/research'
>>>>>>> 1d13ecff676f773be1ed58ca331f0d0b58ce845f

export type LoadPhase = "loading" | "processing" | "ready";

export interface ReportLifecycleState {
	loadPhase: LoadPhase;
	report: ResearchReport | null;
	loadError: string | null;
	showReport: boolean;
	events: ReturnType<typeof useSSE>["events"];
	isComplete: boolean;
	isReconnecting: boolean;
	sseError: string | null;
	cancelled: string | null;
	retrySSE: () => void;
	retryCurrentQuery: () => void;
	retryErrorState: () => void;
	cancelCurrentAnalysis: () => void;
}

export function useReportLifecycle(id: string | undefined, navigate: NavigateFunction): ReportLifecycleState {
<<<<<<< HEAD
	const { t } = useTranslation();
	const [loadPhase, setLoadPhase] = useState<LoadPhase>("loading");
	const [report, setReport] = useState<ResearchReport | null>(null);
	const [loadError, setLoadError] = useState<string | null>(null);
	const [showReport, setShowReport] = useState(false);
=======
  const [loadPhase, setLoadPhase] = useState<LoadPhase>('loading')
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showReport, setShowReport] = useState(false)
  const revealTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
>>>>>>> 1d13ecff676f773be1ed58ca331f0d0b58ce845f

	const {
		events,
		isComplete,
		isReconnecting,
		error: sseError,
		cancelled,
		retry: retrySSE,
	} = useSSE(loadPhase === "processing" ? (id ?? null) : null);

<<<<<<< HEAD
	useEffect(() => {
		if (!id) return;
		getReportWithStatus(id)
			.then((result) => {
				if (result.status === "ready") {
					setLoadError(null);
					setReport(result.report);
					setLoadPhase("ready");
					setTimeout(() => setShowReport(true), 100);
					return;
				}

				setLoadError(null);
				setShowReport(false);
				setReport(null);
				setLoadPhase("processing");
			})
			.catch((error) => {
				setShowReport(false);
				setReport(null);
				setLoadError(error.message);
				setLoadPhase("loading");
			});
	}, [id]);
=======
  const clearRevealTimer = useCallback(() => {
    if (revealTimerRef.current) {
      clearTimeout(revealTimerRef.current)
      revealTimerRef.current = null
    }
  }, [])

  const revealReportSoon = useCallback(() => {
    clearRevealTimer()
    revealTimerRef.current = setTimeout(() => {
      setShowReport(true)
      revealTimerRef.current = null
    }, 100)
  }, [clearRevealTimer])

  useEffect(() => {
    if (!id) return
    getReportWithStatus(id)
      .then(result => {
        if (result.status === 'ready') {
          setLoadError(null)
          setReport(result.report)
          setLoadPhase('ready')
          revealReportSoon()
          return
        }

        setLoadError(null)
        clearRevealTimer()
        setShowReport(false)
        setReport(null)
        setLoadPhase('processing')
      })
      .catch(error => {
        clearRevealTimer()
        setShowReport(false)
        setReport(null)
        setLoadError(error.message)
        setLoadPhase('loading')
      })
  }, [clearRevealTimer, id, revealReportSoon])
>>>>>>> 1d13ecff676f773be1ed58ca331f0d0b58ce845f

	useEffect(() => {
		if (!id || loadPhase !== "processing" || !isComplete) return;
		if (cancelled || sseError) return;

<<<<<<< HEAD
		getReportWithStatus(id)
			.then((result) => {
				if (result.status !== "ready") return;
				setReport(result.report);
				setLoadPhase("ready");
				setTimeout(() => setShowReport(true), 100);
			})
			.catch((error) => setLoadError(error.message));
	}, [cancelled, id, isComplete, loadPhase, sseError]);
=======
    getReportWithStatus(id)
      .then(result => {
        if (result.status !== 'ready') return
        setReport(result.report)
        setLoadPhase('ready')
        revealReportSoon()
      })
      .catch(error => setLoadError(error.message))
  }, [cancelled, id, isComplete, loadPhase, revealReportSoon, sseError])
>>>>>>> 1d13ecff676f773be1ed58ca331f0d0b58ce845f

	const retryWithQuery = useCallback(
		(query: string | undefined) => {
			if (!query) return;

			setLoadError(null);
			startAnalysis(query)
				.then(({ report_id }) => navigate(`/reports/${report_id}`))
				.catch((error) => {
					setLoadError(error instanceof Error ? error.message : t("report.error.restart"));
				});
		},
		[navigate, t],
	);

	const retryCurrentQuery = useCallback(() => {
		retryWithQuery(report?.query);
	}, [report?.query, retryWithQuery]);

	const retryErrorState = useCallback(() => {
		setLoadError(null);
		if (!id) return;

<<<<<<< HEAD
		getReportWithStatus(id)
			.then((result) => {
				if (result.status === "ready") {
					setReport(result.report);
					setLoadPhase("ready");
					setShowReport(true);
					return;
				}

				setLoadPhase("processing");
				retrySSE();
			})
			.catch(() => retrySSE());
	}, [id, retrySSE]);
=======
    getReportWithStatus(id)
      .then(result => {
        if (result.status === 'ready') {
          clearRevealTimer()
          setReport(result.report)
          setLoadPhase('ready')
          setShowReport(true)
          return
        }

        setLoadPhase('processing')
        retrySSE()
      })
      .catch(() => retrySSE())
  }, [clearRevealTimer, id, retrySSE])
>>>>>>> 1d13ecff676f773be1ed58ca331f0d0b58ce845f

	const cancelCurrentAnalysis = useCallback(() => {
		if (!id) return;
		cancelAnalysis(id).catch((error) => {
			setLoadError(error instanceof Error ? error.message : t("report.error.cancel"));
		});
	}, [id, t]);

<<<<<<< HEAD
	return {
		loadPhase,
		report,
		loadError,
		showReport,
		events,
		isComplete,
		isReconnecting,
		sseError,
		cancelled,
		retrySSE,
		retryCurrentQuery,
		retryErrorState,
		cancelCurrentAnalysis,
	};
=======
  useEffect(() => () => clearRevealTimer(), [clearRevealTimer])

  return {
    loadPhase,
    report,
    loadError,
    showReport,
    events,
    isComplete,
    isReconnecting,
    sseError,
    cancelled,
    retrySSE,
    retryCurrentQuery,
    retryErrorState,
    cancelCurrentAnalysis,
  }
>>>>>>> 1d13ecff676f773be1ed58ca331f0d0b58ce845f
}
