import { useState, useCallback } from 'react';
import type { AuditFilterPreset } from '../types';

const STORAGE_KEY = 'shellguard:audit-filter-presets';
const MAX_PRESETS = 20;

function loadPresets(): AuditFilterPreset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as AuditFilterPreset[];
  } catch {
    return [];
  }
}

function persistPresets(presets: AuditFilterPreset[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
}

export function useFilterPresets() {
  const [presets, setPresets] = useState<AuditFilterPreset[]>(loadPresets);

  const savePreset = useCallback(
    (preset: Omit<AuditFilterPreset, 'id' | 'createdAt'>) => {
      setPresets((prev) => {
        const entry: AuditFilterPreset = {
          ...preset,
          id: crypto.randomUUID(),
          createdAt: new Date().toISOString(),
        };
        const next = [entry, ...prev].slice(0, MAX_PRESETS);
        persistPresets(next);
        return next;
      });
    },
    []
  );

  const deletePreset = useCallback((id: string) => {
    setPresets((prev) => {
      const next = prev.filter((p) => p.id !== id);
      persistPresets(next);
      return next;
    });
  }, []);

  return { presets, savePreset, deletePreset };
}
