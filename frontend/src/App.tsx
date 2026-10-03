import { Route, Routes } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import AIChat from "./pages/AIChat";
import AILab from "./pages/AILab";
import Home from "./pages/Home";
import Markets from "./pages/Markets";
import PaperAnalysis from "./pages/PaperAnalysis";
import Screener from "./pages/Screener";
import StockDetails from "./pages/StockDetails";
import Watchlist from "./pages/Watchlist";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Home />} />
        <Route path="markets" element={<Markets />} />
        <Route path="chart" element={<StockDetails />} />
        <Route path="chart/:symbol" element={<StockDetails />} />
        <Route path="watchlist" element={<Watchlist />} />
        <Route path="screener" element={<Screener />} />
        <Route path="lab" element={<AILab />} />
        <Route path="ai" element={<AIChat />} />
        <Route path="paper" element={<PaperAnalysis />} />
        <Route path="*" element={<Home />} />
      </Route>
    </Routes>
  );
}
