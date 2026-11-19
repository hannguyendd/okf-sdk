import * as Dialog from "@radix-ui/react-dialog";
import { createContext, ReactNode, useContext, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Btn } from "../doodle/Btn";
import { Sketch } from "../doodle/Sketch";

export interface Field {
  name: string; label: string; initial?: string; required?: boolean; multiline?: boolean; placeholder?: string; hint?: string;
  /** Render a select with these choices instead of a text input. */
  options?: { value: string; label: string }[];
}
interface FormOptions { title: string; fields: Field[]; submitLabel?: string }
interface PromptOptions { title: string; label: string; initial?: string; multiline?: boolean; required?: boolean; submitLabel?: string }
interface ConfirmOptions { title: string; message: ReactNode; confirmLabel?: string; danger?: boolean }

type Values = Record<string, string>;
type Request =
  | ({ kind: "form"; resolve: (v: Values | null) => void } & FormOptions)
  | ({ kind: "confirm"; resolve: (v: boolean) => void } & ConfirmOptions);

interface Dialogs {
  /** Ask for several text fields; resolves `null` when cancelled. */
  form(o: FormOptions): Promise<Values | null>;
  /** Ask for one line of text; resolves `null` when cancelled. */
  prompt(o: PromptOptions): Promise<string | null>;
  confirm(o: ConfirmOptions): Promise<boolean>;
}

const Ctx = createContext<Dialogs | null>(null);

export function useDialogs(): Dialogs {
  const d = useContext(Ctx);
  if (!d) throw new Error("useDialogs outside DialogProvider");
  return d;
}

/** Promise-based form/prompt/confirm dialogs drawn as a doodled sheet of paper. */
export function DialogProvider({ children }: { children: ReactNode }) {
  const [req, setReq] = useState<Request | null>(null);
  const dialogs = useMemo<Dialogs>(() => {
    const form = (o: FormOptions) => new Promise<Values | null>((resolve) => setReq({ kind: "form", ...o, resolve }));
    return {
      form,
      prompt: async ({ label, initial, multiline, required, ...o }) => {
        const v = await form({ ...o, fields: [{ name: "value", label, initial, multiline, required }] });
        return v ? v.value : null;
      },
      confirm: (o) => new Promise((resolve) => setReq({ kind: "confirm", ...o, resolve })),
    };
  }, []);

  const finish = (value: Values | boolean | null) => {
    if (req?.kind === "form") req.resolve(value && typeof value === "object" ? value : null);
    else if (req?.kind === "confirm") req.resolve(value === true);
    setReq(null);
  };

  return (
    <Ctx.Provider value={dialogs}>
      {children}
      <Dialog.Root open={!!req} onOpenChange={(open) => { if (!open) finish(null); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-[#1b2433]/40 backdrop-blur-[1px]" />
          <Dialog.Content aria-describedby={undefined} className="fixed top-[18%] left-1/2 z-50 w-[min(92vw,500px)] -translate-x-1/2 outline-none">
            <Sketch className="-rotate-1 bg-paper p-6" rough={{ strokeWidth: 2.4 }}>
              {req && <Dialog.Title className="mb-3 font-head text-2xl font-bold">{req.title}</Dialog.Title>}
              {req?.kind === "form" && <FormBody req={req} onDone={finish} />}
              {req?.kind === "confirm" && (
                <>
                  <div className="mb-5">{req.message}</div>
                  <div className="flex justify-end gap-3">
                    <Btn tone="blue" tilt={1} onClick={() => finish(false)}>Cancel</Btn>
                    <Btn tone={req.danger ? "red" : "green"} autoFocus onClick={() => finish(true)}>{req.confirmLabel ?? "OK"}</Btn>
                  </div>
                </>
              )}
            </Sketch>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </Ctx.Provider>
  );
}

function FormBody({ req, onDone }: { req: FormOptions; onDone: (v: Values | null) => void }) {
  const { register, handleSubmit, formState: { errors } } = useForm<Values>({
    defaultValues: Object.fromEntries(req.fields.map((f) => [f.name, f.initial ?? ""])),
  });
  return (
    <form onSubmit={handleSubmit((v) => onDone(v))} className="flex flex-col gap-4">
      {req.fields.map((f, i) => {
        const field = register(f.name, { required: f.required });
        const hintId = f.hint ? `${f.name}-hint` : undefined;
        const props = { autoFocus: i === 0, placeholder: f.placeholder, "aria-describedby": hintId, ...field };
        return (
          <div key={f.name} className="flex flex-col gap-0.5">
            <label className="field">
              {f.label}
              {f.options
                ? <select className="field-line cursor-pointer" {...props}>{f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
                : f.multiline ? <textarea rows={3} className="field-box" {...props} /> : <input className="field-line" {...props} />}
            </label>
            {f.hint && <span id={hintId} className="font-hand text-sm text-ink/50">{f.hint}</span>}
            {errors[f.name] && <span role="alert" className="font-hand text-sm text-red-600">Required, sorry.</span>}
          </div>
        );
      })}
      <div className="flex justify-end gap-3">
        <Btn tone="blue" tilt={1} onClick={() => onDone(null)}>Cancel</Btn>
        <Btn tone="green" type="submit">{req.submitLabel ?? "OK"}</Btn>
      </div>
    </form>
  );
}
