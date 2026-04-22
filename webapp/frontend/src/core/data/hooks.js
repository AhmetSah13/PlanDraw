import { useMutation } from "@tanstack/react-query";
import { alignService, executeService, planService, prepareService } from "./services.js";

export function useImportDxfMutation() {
  return useMutation({ mutationFn: prepareService.importDxf });
}

export function useImportDwgMutation() {
  return useMutation({ mutationFn: prepareService.importDwg });
}

export function useImportJsonMutation() {
  return useMutation({ mutationFn: prepareService.importJson });
}

export function useCompilePlanMutation() {
  return useMutation({ mutationFn: prepareService.compilePlan });
}

export function useAnalyzeMutation() {
  return useMutation({ mutationFn: prepareService.analyze });
}

export function useAlignMutation() {
  return useMutation({ mutationFn: alignService.run });
}

export function useOptimizeMutation() {
  return useMutation({ mutationFn: planService.optimize });
}

export function useSimulateMutation() {
  return useMutation({ mutationFn: planService.simulate });
}

export function useCreateJobMutation() {
  return useMutation({ mutationFn: executeService.createJob });
}

export function useStopJobMutation() {
  return useMutation({ mutationFn: executeService.stopJob });
}

export function useExecuteSerialMutation() {
  return useMutation({
    mutationFn: ({ commandsText, dryRun }) => executeService.executeSerial(commandsText, dryRun),
  });
}
