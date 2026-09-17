import { JudgmentClient, judgeFromEnv, type Judge, type JudgmentClientOptions } from "@overclock/judgment-core";

let defaultClient: JudgmentClient | undefined;

export interface ConfigureOptions extends Partial<Omit<JudgmentClientOptions, "judge">> {
  /** A judge, or a ready client. Without either, judgeFromEnv() decides (replay fixtures, record, or live). */
  judge?: Judge;
  client?: JudgmentClient;
}

/** Set the client every semantic() schema, matcher, and helper uses when none is passed explicitly. */
export function configure(options: ConfigureOptions = {}): JudgmentClient {
  if (options.client) {
    defaultClient = options.client;
    return defaultClient;
  }
  const { judge, client: _ignored, ...rest } = options;
  defaultClient = new JudgmentClient({ judge: judge ?? judgeFromEnv(), ...rest });
  return defaultClient;
}

export function getClient(explicit?: JudgmentClient): JudgmentClient {
  if (explicit) return explicit;
  if (!defaultClient) defaultClient = new JudgmentClient({ judge: judgeFromEnv() });
  return defaultClient;
}

/** Forget the default client (tests). */
export function resetClient(): void {
  defaultClient = undefined;
}
