"use client";

import { AnimatePresence, motion } from "framer-motion";
import { JourneyMapTab } from "./JourneyMapTab";
import { NotesTab } from "./notes/NotesTab";
import { PlannerTab } from "./planner/PlannerTab";
import { useRoadmapNav } from "./RoadmapNavContext";

export function RoadmapView() {
  // 좌측 사이드바(셸)와 공유하는 서브탭 상태.
  const { subTab } = useRoadmapNav();

  return (
    <div className="min-h-[calc(100vh-220px)] space-y-6">
      <AnimatePresence mode="wait">
        <motion.div
          key={subTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
        >
          {subTab === "journey" ? (
            <JourneyMapTab />
          ) : subTab === "planner" ? (
            <PlannerTab />
          ) : (
            <NotesTab />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
