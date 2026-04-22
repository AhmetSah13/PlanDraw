import { TR_COPY } from "./tr/copy";

export const COPY = TR_COPY;

export const STAGE_LIST = [
  COPY.asamalar.planYukle,
  COPY.asamalar.hizala,
  COPY.asamalar.kontrolEt,
  COPY.asamalar.calistir,
  COPY.asamalar.sonuclar
] as const;

export function getStageByPath(pathname: string) {
  return STAGE_LIST.find((asama) => asama.yol === pathname) ?? null;
}
