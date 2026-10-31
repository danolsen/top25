import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { AuthProvider } from "./auth";
import { SportProvider } from "./sport";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <SportProvider>
          <App />
        </SportProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
