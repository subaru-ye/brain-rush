import { createHistoryRecord, getHistoryRecord, getHistoryRecords } from "@/services/api"
import { ensureAuthSession } from "@/services/auth"
import type { LearningRecordDetail, LearningRecordSummary, QuizSession } from "@/types/learning"

export async function saveLearningRecordToHistory(
  session: QuizSession & { report: NonNullable<QuizSession["report"]> }
): Promise<LearningRecordDetail> {
  const auth = await ensureAuthSession()
  const response = await createHistoryRecord(session, auth.token)
  return response.record
}

export async function loadHistoryRecords(): Promise<LearningRecordSummary[]> {
  const auth = await ensureAuthSession()
  const response = await getHistoryRecords(auth.token)
  return response.records
}

export async function loadHistoryRecord(recordId: string): Promise<LearningRecordDetail> {
  const auth = await ensureAuthSession()
  return getHistoryRecord(recordId, auth.token)
}
