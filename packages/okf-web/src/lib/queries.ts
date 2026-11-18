import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, Scope } from "./api";
import { useScope } from "./scope";

/** Query keys. Everything for one workspace lives under `["ws", ws]`. */
export const keys = {
  info: ["info"] as const,
  workspaces: ["workspaces"] as const,
  ws: (s: Scope) => ["ws", s.ws] as const,
  tree: (s: Scope, dir: string) => [...keys.ws(s), "tree", dir] as const,
  concept: (s: Scope, id: string) => [...keys.ws(s), "concept", id] as const,
  search: (s: Scope, q: string) => [...keys.ws(s), "search", q] as const,
  overview: (s: Scope) => [...keys.ws(s), "overview"] as const,
  dirs: (s: Scope) => [...keys.ws(s), "dirs"] as const,
};

export const useInfo = () => useQuery({ queryKey: keys.info, queryFn: api.info, staleTime: Infinity });
export const useReadOnly = () => useInfo().data?.read_only ?? true;
export const useWorkspaces = () => useQuery({ queryKey: keys.workspaces, queryFn: api.workspaces });

export function useTree(dir: string, enabled = true) {
  const s = useScope();
  return useQuery({ queryKey: keys.tree(s, dir), queryFn: () => api.tree(s, dir), enabled });
}
export function useConcept(id: string) {
  const s = useScope();
  return useQuery({ queryKey: keys.concept(s, id), queryFn: () => api.concept(s, id) });
}
export function useSearch(q: string, enabled = true) {
  const s = useScope();
  return useQuery({ queryKey: keys.search(s, q), queryFn: () => api.search(s, q), retry: false, enabled });
}

/**
 * A write against the current workspace. On success every cached read of that
 * workspace (tree, concepts, search, overview, workspace list) is refetched — writes
 * regenerate `_index.md` files, so partial invalidation isn't worth it.
 * `done` returns the toast to show on success (brand voice, see BRAND.md §8).
 */
export function useScopeMutation<V, R>(fn: (s: Scope, vars: V) => Promise<R>, done?: (result: R, vars: V) => string | null) {
  const s = useScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: V) => fn(s, vars),
    onSuccess: (result, vars) => {
      const msg = done?.(result, vars);
      if (msg) toast(msg);
      // Not awaited: callers navigate right after the write (e.g. away from a
      // deleted concept) before the refetch lands, so nothing flashes an error.
      void invalidateWorkspace();
    },
  });
  function invalidateWorkspace() {
    return Promise.all([
      qc.invalidateQueries({ queryKey: keys.ws(s) }),
      qc.invalidateQueries({ queryKey: keys.workspaces }),
    ]);
  }
}

/** Every directory in the current workspace (for folder pickers). */
export function useDirs(enabled = true) {
  const s = useScope();
  return useQuery({ queryKey: keys.dirs(s), queryFn: () => api.dirs(s), enabled });
}

/** Concept/folder counts, types, and recent concepts of the current workspace. */
export function useOverview() {
  const s = useScope();
  return useQuery({ queryKey: keys.overview(s), queryFn: () => api.overview(s) });
}

export function useWorkspaceMutation<V, R>(fn: (vars: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: keys.workspaces }) });
}

/** Warm the cache on hover/focus so a click lands on loaded data. */
export function usePrefetch() {
  const qc = useQueryClient();
  const fresh = 30_000; // don't refetch on every hover
  return {
    workspace: (s: Scope) => {
      qc.prefetchQuery({ queryKey: keys.overview(s), queryFn: () => api.overview(s), staleTime: fresh });
      qc.prefetchQuery({ queryKey: keys.tree(s, ""), queryFn: () => api.tree(s, ""), staleTime: fresh });
    },
    dir: (s: Scope, dir: string) =>
      qc.prefetchQuery({ queryKey: keys.tree(s, dir), queryFn: () => api.tree(s, dir), staleTime: fresh }),
    concept: (s: Scope, id: string) =>
      qc.prefetchQuery({ queryKey: keys.concept(s, id), queryFn: () => api.concept(s, id), staleTime: fresh }),
  };
}
