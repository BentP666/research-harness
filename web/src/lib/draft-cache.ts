/**
 * Tiny IndexedDB wrapper for offline draft caching.
 *
 * Store: 'drafts' — keyed by `${topicId}:${section}` with { content, saved_at }
 *
 * Why IndexedDB (not localStorage): drafts can exceed the ~5MB localStorage
 * cap; also async API is a better fit for larger payloads.
 */

const DB_NAME = "atlas-offline";
const DB_VERSION = 1;
const STORE = "drafts";

type DraftRecord = {
  key: string;
  topic_id: number;
  section: string;
  content: string;
  saved_at: string;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB not available"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "key" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function tx<T>(
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest<T> | Promise<T>
): Promise<T> {
  return new Promise((resolve, reject) => {
    openDb()
      .then((db) => {
        const t = db.transaction(STORE, mode);
        const store = t.objectStore(STORE);
        const maybe = run(store);
        if (maybe instanceof Promise) {
          maybe.then(resolve, reject);
          t.oncomplete = () => db.close();
          return;
        }
        maybe.onsuccess = () => {
          resolve(maybe.result);
          db.close();
        };
        maybe.onerror = () => {
          reject(maybe.error);
          db.close();
        };
      })
      .catch(reject);
  });
}

export async function saveDraft(
  topicId: number,
  section: string,
  content: string
): Promise<void> {
  try {
    await tx("readwrite", (store) => {
      const rec: DraftRecord = {
        key: `${topicId}:${section}`,
        topic_id: topicId,
        section,
        content,
        saved_at: new Date().toISOString(),
      };
      return store.put(rec);
    });
  } catch (err) {
    // Silently ignore — offline cache is best-effort
    console.warn("draft cache save failed", err);
  }
}

export async function loadDraft(
  topicId: number,
  section: string
): Promise<DraftRecord | null> {
  try {
    const rec = await tx<DraftRecord | undefined>("readonly", (store) =>
      store.get(`${topicId}:${section}`)
    );
    return rec ?? null;
  } catch (err) {
    console.warn("draft cache load failed", err);
    return null;
  }
}

export async function listDrafts(topicId: number): Promise<DraftRecord[]> {
  try {
    return await tx<DraftRecord[]>("readonly", (store) => {
      return new Promise<DraftRecord[]>((resolve, reject) => {
        const out: DraftRecord[] = [];
        const cursor = store.openCursor();
        cursor.onsuccess = () => {
          const c = cursor.result;
          if (c) {
            const v = c.value as DraftRecord;
            if (v.topic_id === topicId) out.push(v);
            c.continue();
          } else {
            resolve(out);
          }
        };
        cursor.onerror = () => reject(cursor.error);
      });
    });
  } catch {
    return [];
  }
}

export async function deleteDraft(
  topicId: number,
  section: string
): Promise<void> {
  try {
    await tx("readwrite", (store) => store.delete(`${topicId}:${section}`));
  } catch {
    // ignore
  }
}
