"use client";

import { useEffect, useRef, useState } from "react";

/** Counts 0 → target once, the first time a real value arrives. */
export function useCountUp(target: number, reduced: boolean): number {
  const [val, setVal] = useState(0);
  const animated = useRef(false);

  useEffect(() => {
    if (reduced || target <= 0 || animated.current) {
      setVal(target);
      return;
    }
    animated.current = true;
    const t0 = performance.now();
    const dur = 1200;
    let raf: number;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / dur);
      setVal(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, reduced]);

  return val;
}
