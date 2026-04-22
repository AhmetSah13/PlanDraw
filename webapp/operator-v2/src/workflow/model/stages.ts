export type OperatorStage =
  | "plan-yukle"
  | "hizala"
  | "kontrol-et"
  | "calistir"
  | "sonuclar";

export const OPERATOR_STAGE_SEQUENCE: OperatorStage[] = [
  "plan-yukle",
  "hizala",
  "kontrol-et",
  "calistir",
  "sonuclar"
];
