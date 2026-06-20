declare module 'node:sqlite' {
  interface RunResult {
    changes: number;
    lastInsertRowid: number | bigint;
  }

  class StatementSync {
    get(...params: unknown[]): unknown;
    run(...params: unknown[]): RunResult;
    all(...params: unknown[]): unknown[];
  }

  class DatabaseSync {
    constructor(location: string, options?: { open?: boolean; readOnly?: boolean });
    exec(sql: string): void;
    prepare(sql: string): StatementSync;
    close(): void;
  }

  export { DatabaseSync, StatementSync, RunResult };
}
