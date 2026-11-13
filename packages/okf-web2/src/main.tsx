import "@fontsource/mali/400.css";
import "@fontsource/mali/600.css";
import "@fontsource/mali/700.css";
import "@fontsource/patrick-hand/400.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./app.css";

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
