/**
 * Offline queue (SQLite). Inspections and uploads made without network are stored and replayed
 * when connectivity returns (called from the home screen and on app foreground).
 */
import * as SQLite from "expo-sqlite";
import * as FileSystem from "expo-file-system";
import { cases } from "@/api/endpoints";
import { uploadMedia } from "./capture";

let db: SQLite.SQLiteDatabase | null = null;
async function open() {
  if (db) return db;
  db = await SQLite.openDatabaseAsync("bvms.db");
  await db.execAsync(`CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, payload TEXT, created_at TEXT, attempts INTEGER DEFAULT 0, last_error TEXT);`);
  return db;
}
export async function enqueue(kind: "case" | "media", payload: any) {
  const d = await open();
  await d.runAsync("INSERT INTO queue (kind, payload, created_at) VALUES (?, ?, ?)", kind, JSON.stringify(payload), new Date().toISOString());
}
export async function pending(): Promise<number> {
  const d = await open();
  const r = await d.getFirstAsync<{ n: number }>("SELECT COUNT(*) as n FROM queue");
  return r?.n ?? 0;
}
export async function sync(): Promise<{ done: number; failed: number }> {
  const d = await open();
  const rows = await d.getAllAsync<{ id: number; kind: string; payload: string; attempts: number }>("SELECT * FROM queue ORDER BY id");
  let done = 0, failed = 0;
  for (const row of rows) {
    const p = JSON.parse(row.payload);
    try {
      if (row.kind === "case") {
        // upload queued media first, then create the case with their ids
        const ids: string[] = [];
        for (const m of p.media || []) { const info = await FileSystem.getInfoAsync(m.file.uri); if (!info.exists) continue; const up = await uploadMedia(m.file, m.kind, { fix: m.fix }); ids.push(up.id); }
        await cases.create({ ...p.data, media_ids: ids });
      } else if (row.kind === "media") {
        await uploadMedia(p.file, p.kind, { caseId: p.caseId, noticeId: p.noticeId, fix: p.fix, caption: p.caption });
      }
      await d.runAsync("DELETE FROM queue WHERE id = ?", row.id);
      done++;
    } catch (e: any) {
      failed++;
      await d.runAsync("UPDATE queue SET attempts = attempts + 1, last_error = ? WHERE id = ?", String(e?.message || e).slice(0, 300), row.id);
    }
  }
  return { done, failed };
}
