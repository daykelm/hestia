import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getJSON, SignedOut, type Deal, type Guide } from "./api";

type Store = {
  deals: Deal[];
  guide: Guide | null;
  loading: boolean;
  error: string;
  signedOut: boolean;
  refresh: () => Promise<void>;
  replace: (deal: Deal) => void;
  signedIn: () => void;
};

const Context = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [guide, setGuide] = useState<Guide | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [signedOut, setSignedOut] = useState(false);

  const load = useCallback(
    () =>
      Promise.all([getJSON<Deal[]>("/api/deals"), getJSON<Guide>("/api/guide")])
        .then(([rows, text]) => {
          setDeals(rows);
          setGuide(text);
          setError("");
          setSignedOut(false);
        })
        .catch((err) => {
          if (err instanceof SignedOut) setSignedOut(true);
          else setError("Hestia is out of reach. Check the connection and pull down to try again.");
        })
        .finally(() => setLoading(false)),
    [],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    await load();
  }, [load]);

  useEffect(() => {
    load();
  }, [load]);

  const value = useMemo<Store>(
    () => ({
      deals,
      guide,
      loading,
      error,
      signedOut,
      refresh,
      replace: (deal) => setDeals((rows) => rows.map((row) => (row.id === deal.id ? deal : row))),
      signedIn: () => {
        setSignedOut(false);
        refresh();
      },
    }),
    [deals, guide, loading, error, signedOut, refresh],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useStore() {
  const store = useContext(Context);
  if (!store) throw new Error("useStore needs StoreProvider");
  return store;
}
