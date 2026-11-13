/** Loading indicator: a school notebook flipping open (CSS in app.css). */
export function Loading({ label = "Coming, coming…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-5 py-4 font-head text-lg">
      <div className="book" aria-hidden="true">
        <div className="back" />
        <div className="page p2" />
        <div className="page p1" />
        <div className="cover" />
        <div className="spine" />
      </div>
      <p>{label}</p>
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <p role="alert" className="font-head text-red-600">
      Oops, I dropped my crayons: {error instanceof Error ? error.message : String(error)}
    </p>
  );
}
