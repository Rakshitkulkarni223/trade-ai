import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { addWatch, fetchWatchSymbols, removeWatch } from "../api/ai";

/** Which symbols are in the watchlist. One cheap request, shared by every Watch button. */
export const useWatchSymbols = () => useQuery({ queryKey: ["watchlist-symbols"], queryFn: fetchWatchSymbols, staleTime: 15_000 });

/** The Watch button for one symbol. Its state comes from the real watchlist, not from "did I just click it". */
export function useWatchToggle(symbol: string) {
  const qc = useQueryClient();
  const list = useWatchSymbols();
  const watching = !!list.data?.symbols.includes(symbol.toUpperCase());
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["watchlist"] });
    qc.invalidateQueries({ queryKey: ["watchlist-symbols"] });
  };
  const add = useMutation({ mutationFn: () => addWatch(symbol), onSuccess: refresh });
  const remove = useMutation({ mutationFn: () => removeWatch(symbol), onSuccess: refresh });
  // The header stays mounted while you move between symbols, so a result or error must not follow you to the next one.
  useEffect(() => { add.reset(); remove.reset(); }, [symbol]);     // eslint-disable-line react-hooks/exhaustive-deps
  return {
    watching, ready: !!list.data, pending: add.isPending || remove.isPending,
    error: ((add.error ?? remove.error) as Error | null)?.message ?? null,
    toggle: () => (watching ? remove : add).mutate(),
  };
}
