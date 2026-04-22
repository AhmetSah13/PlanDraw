import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./app/App.jsx";
import { WorkflowProvider } from "./core/workflow/WorkflowProvider.jsx";
import "./shared/styles/global.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
    mutations: { retry: 0 },
  },
});

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <WorkflowProvider>
        <App />
      </WorkflowProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
