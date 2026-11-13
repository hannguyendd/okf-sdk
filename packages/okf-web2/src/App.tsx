import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { flushSync } from "react-dom";
import { Toaster } from "sonner";
import { AroundNavHandler, Link, Route, Router, Switch } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import { DialogProvider } from "./components/Dialogs";
import { Intro } from "./components/Intro";
import { Logo } from "./components/Logo";
import { Doodles } from "./doodle/Doodles";
import { Okie } from "./doodle/Okie";
import { ScopeProvider, param } from "./lib/scope";
import { IndexLayout } from "./pages/IndexLayout";
import { WorkspacePage } from "./pages/WorkspacePage";
import { WorkspacesPage } from "./pages/WorkspacesPage";

/**
 * Routes (hash-based, so the API server only has to serve index.html):
 *   #/                         workspaces
 *   #/w/:ws                    one workspace: its notebooks and recent concepts
 *   #/w/:ws/:index/            index root      …/d/<dir>   directory
 *   …/c/<id> concept   …/e/<id> edit   …/n/<dir> new concept   …/s/<q> search
 */
/** Animate route changes as a page turn where View Transitions are supported. */
const pageTurn: AroundNavHandler = (navigate, to, opts) => {
  if (!document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return navigate(to, opts);
  document.startViewTransition(() => flushSync(() => navigate(to, opts)));
};

export function App({ client }: { client?: QueryClient }) {
  const [qc] = useState(() => client ?? new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 5_000, refetchOnWindowFocus: false } } }));
  return (
    <QueryClientProvider client={qc}>
      <DialogProvider>
        <Intro />
        <Doodles />
        <Toaster position="bottom-right" toastOptions={{ unstyled: true, classNames: { toast: "toast-note" } }} />
        <Router hook={useHashLocation} aroundNav={pageTurn}>
          <Switch>
            <Route path="/"><WorkspacesPage /></Route>
            <Route path="/w/:ws">{(p) => <WorkspacePage key={p.ws} ws={param(p.ws)} />}</Route>
            <Route path="/w/:ws/:index" nest>
              {(p) => {
                const scope = { ws: param(p.ws), index: param(p.index) };
                return <ScopeProvider key={`${scope.ws}/${scope.index}`} scope={scope}><IndexLayout /></ScopeProvider>;
              }}
            </Route>
            <Route>
              <div className="mx-auto max-w-4xl p-6">
                <Logo />
                <div className="mt-10 flex flex-wrap items-center gap-6">
                  <Okie pose="lost-page" size={220} />
                  <p className="font-head text-xl">This page fell out of the notebook. <Link href="/">Back to workspaces</Link></p>
                </div>
              </div>
            </Route>
          </Switch>
        </Router>
      </DialogProvider>
    </QueryClientProvider>
  );
}
