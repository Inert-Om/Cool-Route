import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "leaflet/dist/leaflet.css";
import "./index.css";

import LandingPage from "./App.jsx";
import MapPage from "./Map.jsx";

const Page = window.location.pathname === "/map"
  ? MapPage
  : LandingPage;

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Page />
  </StrictMode>
);