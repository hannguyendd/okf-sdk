import { AnimatePresence, motion, MotionConfig, useScroll, useSpring, useTransform } from "motion/react";
import { AnchorHTMLAttributes, ReactNode, useState } from "react";
import { ThemeToggle } from "../components/ThemeToggle";
import { DoodleIcon, IconName } from "../doodle/DoodleIcon";
import { Mark } from "../doodle/Mark";
import { markUrl, Okie, OkieSketch, Pose } from "../doodle/Okie";
import { crayon, scribble, Sketch, Tone } from "../doodle/Sketch";

const REPO = "https://github.com/hannguyendd/okf-sdk";
const DOCS = `${REPO}/blob/okf-web-v2/docs/TECHNICAL.md`;

/** Landing art and screenshots (src/assets/landing), picked up when present; Okie poses fill any gap. */
const art = import.meta.glob<string>("../assets/landing/*.{png,webp}", { eager: true, query: "?url", import: "default" });
const img = (name: string) => art[`../assets/landing/${name}`];
const decor = import.meta.glob<string>("../assets/doodles/decor/*.png", { eager: true, query: "?url", import: "default" });

/** A margin doodle (sun, cloud, paper plane…) that scrolls with its section and drifts a little. */
function Decor({ name, className }: { name: string; className: string }) {
  const src = decor[`../assets/doodles/decor/${name}.png`];
  return src ? <img src={src} alt="" aria-hidden="true" style={{ animationDelay: `${-name.length * 0.7}s` }}
    className={`decor-drift pointer-events-none absolute hidden select-none lg:block ${className}`} /> : null;
}

const ease = [0.22, 1, 0.36, 1] as const;
const VIEW = { once: true, margin: "-60px" } as const;

/** Slides its children up into place the first time they scroll into view. */
function Reveal({ children, delay = 0, x = 0, className }: { children: ReactNode; delay?: number; x?: number; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, x, y: x ? 0 : 28 }} whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={VIEW} transition={{ duration: 0.7, ease, delay }}>
      {children}
    </motion.div>
  );
}

/** A sticker being slapped onto the page: drops in big and crooked, settles flat. */
const stick = (i: number) => ({
  initial: { opacity: 0, scale: 1.2, rotate: i % 2 ? 7 : -7, y: -14 },
  whileInView: { opacity: 1, scale: 1, rotate: 0, y: 0 },
  viewport: VIEW,
  transition: { type: "spring" as const, stiffness: 320, damping: 17, delay: (i % 4) * 0.09 },
});

function GitHubIcon({ size = 22 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden="true">
      <path d="M12 .3a12 12 0 0 0-3.8 23.38c.6.12.83-.26.83-.57l-.02-2.04c-3.34.72-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.08-.74.09-.73.09-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.8 1.3 3.49 1 .1-.78.42-1.3.76-1.6-2.67-.31-5.47-1.34-5.47-5.94 0-1.31.47-2.38 1.24-3.22-.14-.3-.54-1.52.1-3.18 0 0 1-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.28-1.55 3.29-1.23 3.29-1.23.64 1.66.24 2.88.12 3.18a4.65 4.65 0 0 1 1.23 3.22c0 4.61-2.8 5.63-5.48 5.92.43.37.82 1.1.82 2.22l-.02 3.29c0 .32.22.7.83.57A12 12 0 0 0 12 .3" />
    </svg>
  );
}

function StarIcon() {
  return (
    <svg viewBox="0 0 24 24" width={20} height={20} aria-hidden="true" className="star-icon">
      <path d="M12 2.6l2.9 6 6.6.9-4.8 4.6 1.2 6.6L12 17.5l-5.9 3.2 1.2-6.6-4.8-4.6 6.6-.9z"
        fill={crayon.orange} stroke="currentColor" strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
  );
}

function Art({ name, fallback, alt = "", className = "" }: { name: string; fallback: Pose; alt?: string; className?: string }) {
  const src = img(name);
  if (!src) return <Okie pose={fallback} size={420} className={className} />;
  return <img src={src} alt={alt} aria-hidden={alt ? undefined : true} className={`object-contain ${className}`} />;
}

/** A link drawn like a crayon button. */
function LinkBtn({ tone = "yellow", tilt = -1.5, big, className = "", ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { tone?: Tone; tilt?: number; big?: boolean }) {
  return (
    <Sketch as="a" rough={{ ...scribble(tone), roughness: 2.1 }} pad={1} style={{ rotate: `${tilt}deg` }}
      className={`doodle-btn no-wavy inline-block no-underline ${big ? "px-6 text-xl leading-[3rem]" : "px-4 leading-9"} ${className}`} {...props} />
  );
}

function Section({ id, title, kicker, children, className = "" }: { id?: string; title: ReactNode; kicker?: string; children: ReactNode; className?: string }) {
  return (
    <section id={id} className={`relative mx-auto max-w-6xl scroll-mt-24 pr-5 pl-[72px] md:px-5 py-10 md:py-14 ${className}`}>
      <Reveal>
        {kicker && <p className="mb-1 font-head text-sm tracking-widest text-ink/55 uppercase">{kicker}</p>}
        <h2 className="mt-0 mb-8 text-3xl md:text-4xl">{title}</h2>
      </Reveal>
      {children}
    </section>
  );
}

function Nav() {
  return (
    <header className="sticky top-0 z-30 bg-paper/85 backdrop-blur-sm">
      <nav aria-label="Main" className="mx-auto flex max-w-6xl items-center gap-3 px-3 py-2 sm:gap-5 sm:pr-5 sm:pl-[72px] md:px-5">
        <a href="#top" className="no-wavy inline-flex shrink-0 -rotate-2 items-center gap-1 font-head text-xl font-bold whitespace-nowrap text-ink no-underline">
          {markUrl ? <img src={markUrl} alt="" className="-my-4 h-14 w-16 object-contain sm:h-16 sm:w-20" /> : <OkieSketch size={64} />}
          <Mark type="underline" color={crayon.red} strokeWidth={2.5} padding={1}>OK, Fine Memory</Mark>
        </a>
        <div className="ml-auto hidden items-center gap-5 font-head text-ink/80 lg:flex">
          <a href="#how" className="no-wavy text-ink no-underline hover:underline">How it works</a>
          <a href="#look" className="no-wavy text-ink no-underline hover:underline">Look inside</a>
          <a href="#faq" className="no-wavy text-ink no-underline hover:underline">FAQ</a>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3 lg:ml-0">
          <ThemeToggle />
          <Sketch as="a" href={REPO} shape="ellipse" aria-label="GitHub" title="Okie’s code on GitHub" rough={{ strokeWidth: 1.6 }}
            className="no-wavy grid size-10 place-items-center text-ink no-underline hover:[animation:wiggle_0.4s_ease-in-out] motion-reduce:hover:animate-none">
            <GitHubIcon />
          </Sketch>
          <span className="hidden sm:block">
            <LinkBtn href={REPO} tone="yellow" tilt={-2} className="star-btn" title="Star Okie on GitHub">
              <span className="inline-flex items-center gap-1.5"><StarIcon />Star</span>
            </LinkBtn>
          </span>
          <span className="hidden lg:block"><LinkBtn href="#start" tone="green" tilt={1.5}>Wake Okie up</LinkBtn></span>
        </div>
      </nav>
    </header>
  );
}

function Hero() {
  return (
    <section id="top" className="relative mx-auto grid max-w-6xl items-center gap-8 pr-5 pl-[72px] md:px-5 pt-10 pb-6 md:grid-cols-[1.05fr_1fr] md:pt-16">
      <div className="min-w-0">
        <motion.p className="sticky-note mb-6 inline-block -rotate-3 cursor-default text-base"
          initial={{ opacity: 0, y: -40, rotate: -14, scale: 1.2 }} animate={{ opacity: 1, y: 0, rotate: 0, scale: 1 }}
          whileHover={{ rotate: 4, scale: 1.04 }} transition={{ type: "spring", stiffness: 260, damping: 14, delay: 0.1 }}>
          Psst. Your team forgot something again.
        </motion.p>
        <h1 className="-rotate-1 font-head text-5xl leading-[1.15] font-bold md:text-6xl">
          {[<>OK, fine.</>, <>I’ll <Mark type="highlight" color={crayon.yellow} iterations={2}>remember</Mark> it</>, <>for you.</>].map((line, i) => (
            <span key={i}>
              {i > 0 && " "}
              <motion.span className="block" initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease, delay: 0.35 + i * 0.22 }}>
                {line}
              </motion.span>
            </span>
          ))}
        </h1>
        <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease, delay: 1.1 }}>
        <p className="mt-6 max-w-xl text-xl leading-8 text-ink/85">
          Meet <b>Okie</b>, a tired little snail who keeps everything your team knows in neat notebooks.
          You write in the web app, your AI helpers write through MCP, and Okie keeps it all tidy, linked and findable.
          Slowly. With a sigh. But it never forgets.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-5">
          <LinkBtn href="#start" big tone="yellow">Wake Okie up</LinkBtn>
          <LinkBtn href="#how" big tone="blue" tilt={1.2}>How does it work?</LinkBtn>
        </div>
        <p className="mt-5 text-ink/60">Free, open source, runs on your own computer. No account. No cloud. Just a snail.</p>
        </motion.div>
      </div>
      {/* Okie crawls in from the margin, slowly, as snails do */}
      <motion.div className="relative" initial={{ opacity: 0, x: 140 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 2.4, ease: "easeOut", delay: 0.2 }}>
        <Art name="okie-hauling.png" fallback="writing" alt="Okie the snail hauling a huge wobbly stack of notebooks" className="mx-auto w-full max-w-[520px] [animation:okie-bob_3.2s_ease-in-out_infinite]" />
        <motion.span aria-hidden="true" className="absolute top-4 right-6 rotate-6 font-hand text-2xl text-ink/60"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: [0, 1, 1, 0.35, 1], y: [10, 0, -6, 0, 0] }}
          transition={{ duration: 4, delay: 2.5, repeat: Infinity, repeatDelay: 2 }}>
          ~ sigh ~
        </motion.span>
      </motion.div>
      <Decor name="sun" className="top-4 -right-14 w-28" />
      <Decor name="cloud" className="top-12 left-[44%] w-24 opacity-90" />
    </section>
  );
}

const PAINS: [string, Tone, number][] = [
  ["“Where’s the deploy doc?”", "yellow", -3],
  ["“Didn’t we decide this in March?”", "pink", 2],
  ["“Ask Minh, he knows.” (Minh left.)", "green", -1.5],
  ["“It’s in Slack. Somewhere. Probably.”", "blue", 2.5],
  ["“Who set up the printer?”", "orange", -2],
  ["“I’ll write it down later.”", "purple", 1.5],
];

function Pains() {
  return (
    <Section title={<>Sound familiar?</>} kicker="The problem">
      <Decor name="paper-plane" className="top-6 right-0 w-28 rotate-6" />
      <div className="grid items-center gap-10 md:grid-cols-[1.4fr_1fr]">
        <ul className="m-0 grid list-none grid-cols-1 gap-6 p-0 sm:grid-cols-2">
          {PAINS.map(([text, tone, r], i) => (
            <motion.li key={text} {...stick(i)} whileHover={{ rotate: -r, scale: 1.04 }}>
              <Sketch className="crayon-fill px-5 py-4 font-head text-lg shadow-[3px_4px_0_var(--shadow)]" style={{ rotate: `${r}deg`, background: "var(--note)" }}
                rough={{ ...scribble(tone), fillWeight: 1.2, hachureGap: 9, strokeWidth: 1.6 }}>
                {text}
              </Sketch>
            </motion.li>
          ))}
        </ul>
        <Reveal x={60} delay={0.3}>
        <figure className="m-0 text-center">
          <Art name="okie-coffee.png" fallback="sigh" className="mx-auto w-full max-w-[340px] [animation:okie-bob_4s_ease-in-out_infinite]" />
          <figcaption className="mt-2 text-lg text-ink/75">
            Okie has heard every one of these about 400 times.<br />It’s 2am. Okie is still up. Okie would like to stop.
          </figcaption>
        </figure>
        </Reveal>
      </div>
    </Section>
  );
}

const STEPS: { n: string; title: string; body: string; pose: Pose; art?: string; tone: Tone }[] = [
  { n: "1", title: "Tell Okie", body: "Type a note in the notebook app, or let your AI assistant drop it in through MCP. Markdown, a title, a few tags. That’s it.", pose: "wave", tone: "yellow" },
  { n: "2", title: "Okie files it", body: "Into the right notebook and folder. Listings, change logs and links update themselves. Move a page and Okie fixes every link to it.", pose: "writing", tone: "pink" },
  { n: "3", title: "Ask later", body: "Browse the spiral-notebook explorer, follow links both ways, or search in plain words. Okie digs it up. Eventually.", pose: "reading", art: "okie-found-it.png", tone: "green" },
];

function How() {
  return (
    <Section id="how" title="How it works (it’s not hard, Okie is just slow)" kicker="Three steps">
      <ol className="m-0 grid list-none gap-8 p-0 md:grid-cols-3">
        {STEPS.map((s, i) => (
          <motion.li key={s.n} initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={VIEW}
            whileHover={{ y: -6 }} transition={{ duration: 0.7, ease, delay: i * 0.18 }}>
            <Sketch className="flex h-full flex-col items-center bg-paper px-6 pt-4 pb-6 text-center" style={{ rotate: `${[-1, 0.8, -0.6][i]}deg` }} rough={{ strokeWidth: 2.2 }}>
              <motion.div initial={{ scale: 0, rotate: -90 }} whileInView={{ scale: 1, rotate: 0 }} viewport={VIEW}
                transition={{ type: "spring", stiffness: 300, damping: 12, delay: 0.3 + i * 0.18 }}>
                <Sketch shape="ellipse" className="grid size-12 place-items-center font-head text-2xl font-bold" rough={{ ...scribble(s.tone), strokeWidth: 2 }}>{s.n}</Sketch>
              </motion.div>
              {s.art && img(s.art) ? <Art name={s.art} fallback={s.pose} className="my-2 h-44 w-full" /> : <Okie pose={s.pose} size={230} className="my-2 h-44" />}
              <h3 className="font-head text-2xl font-bold">{s.title}</h3>
              <p className="mt-2 text-lg leading-7 text-ink/80">{s.body}</p>
            </Sketch>
          </motion.li>
        ))}
      </ol>
    </Section>
  );
}

function Everyone() {
  return (
    <Section title="Everybody hands Okie their notes" kicker="Humans and robots">
      <div className="grid items-center gap-10 md:grid-cols-[1.3fr_1fr]">
        <Reveal x={-60}><Art name="okie-helping.png" fallback="writing" alt="People handing Okie their notes" className="w-full" /></Reveal>
        <Reveal x={60} delay={0.15} className="flex flex-col gap-5 text-lg leading-8">
          <p>Your teammates use the <b>notebook web app</b>: make notebooks, write pages, drag them into folders, colour-code workspaces with crayons.</p>
          <p>Your AI agents (Claude, or anything that speaks <b>MCP</b>) read and write <i>the same notebooks</i>. They add pages, fix them, move them, and search before they guess.</p>
          <p>Okie keeps it all in plain markdown files on your disk, so nothing is locked in. Open them in any editor. Put them in git. Okie won’t mind. <span className="text-ink/60">(Okie will mind a little.)</span></p>
        </Reveal>
      </div>
    </Section>
  );
}

const SHOTS: { file: string; title: string; caption: string; tone: Tone; tilt: number }[] = [
  { file: "shot-workspace.webp", title: "Notebooks", caption: "Each workspace is a stack of notebooks, plus what Okie remembered most recently.", tone: "blue", tilt: -1.2 },
  { file: "shot-concept.webp", title: "Pages", caption: "The explorer is a real spiral notebook. Drag pages into folders; links get fixed for you.", tone: "pink", tilt: 0.9 },
  { file: "shot-dark.webp", title: "Night shift", caption: "Chalkboard dark mode. Because Okie works late.", tone: "green", tilt: -0.7 },
];

function Look() {
  const [i, setI] = useState(0);
  const shot = SHOTS[i];
  const src = img(shot.file);
  return (
    <Section id="look" title="Take a look inside" kicker="Screenshots">
      <div role="tablist" aria-label="Screenshots" className="mb-6 flex flex-wrap gap-4">
        {SHOTS.map((s, j) => (
          <button key={s.file} role="tab" aria-selected={i === j} onClick={() => setI(j)}
            className={`doodle-btn relative isolate cursor-pointer px-4 leading-9 ${i === j ? "" : "text-ink/70"}`}>
            {i === j && <motion.span layoutId="shot-tab" aria-hidden="true" className="absolute inset-0 -z-10 rounded-full border-2 border-dashed border-ink bg-note"
              transition={{ type: "spring", stiffness: 380, damping: 30 }} />}
            {s.title}
          </button>
        ))}
      </div>
      <figure role="tabpanel" className="m-0">
        <motion.div animate={{ rotate: shot.tilt }} transition={{ type: "spring", stiffness: 200, damping: 14 }}>
        <Sketch className="relative bg-paper p-3 md:p-4" rough={{ strokeWidth: 2.4 }}>
          <span aria-hidden="true" className="tape tape-l" style={{ ["--accent" as string]: crayon[shot.tone] }} />
          <span aria-hidden="true" className="tape tape-r" style={{ ["--accent" as string]: crayon[shot.tone] }} />
          {/* switching tabs turns the page: the old shot flips away, the new one flips in */}
          <div className="aspect-[16/10] overflow-hidden rounded-sm [perspective:1400px]">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={shot.file} className="size-full origin-left"
                initial={{ opacity: 0, rotateY: 55, x: 30 }} animate={{ opacity: 1, rotateY: 0, x: 0 }} exit={{ opacity: 0, rotateY: -55, x: -30 }}
                transition={{ duration: 0.35, ease }}>
                {src
                  ? <img src={src} alt={shot.caption} className="block size-full object-cover object-top" />
                  : <div className="grid size-full place-items-center text-ink/50">screenshot coming soon</div>}
              </motion.div>
            </AnimatePresence>
          </div>
        </Sketch>
        </motion.div>
        <figcaption className="mt-4 text-center text-lg text-ink/75">{shot.caption}</figcaption>
      </figure>
    </Section>
  );
}

const FEATURES: { icon: IconName; title: string; body: string; tone: Tone }[] = [
  { icon: "notebook", title: "Notebooks & folders", body: "Make them, fill them, drag pages between them.", tone: "blue" },
  { icon: "pencil", title: "Plain markdown", body: "Titles, tags, tables, links. Just text files on your disk.", tone: "yellow" },
  { icon: "link", title: "Links both ways", body: "Every page shows what it links to, and who links back.", tone: "pink" },
  { icon: "search", title: "Search in normal words", body: "Plug in a local embeddings server and just ask.", tone: "green" },
  { icon: "refresh", title: "Self-tidying", body: "Listings and change logs rewrite themselves after every edit.", tone: "orange" },
  { icon: "palette", title: "Crayon colours", body: "Seven crayons, one per workspace. Choose wisely.", tone: "purple" },
  { icon: "move", title: "MCP for AI agents", body: "Claude and friends read and write the same notebooks.", tone: "red" },
  { icon: "check", title: "Stays on your machine", body: "No cloud, no login, no tracking. Just a snail.", tone: "green" },
];

function Features() {
  return (
    <Section title="What’s in Okie’s shell" kicker="Features">
      <Decor name="rainbow" className="top-2 right-4 w-36" />
      <ul className="m-0 grid list-none gap-6 p-0 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map((f, i) => (
          <motion.li key={f.title} {...stick(i)} whileHover={{ y: -5, rotate: i % 2 ? 1.5 : -1.5 }}>
            <Sketch className="h-full bg-paper px-5 py-4" style={{ rotate: `${(i % 3) - 1}deg` }} rough={{ strokeWidth: 2 }}>
              <div className="mb-1 flex items-center gap-2">
                <Sketch shape="ellipse" className="grid size-11 shrink-0 place-items-center" rough={{ ...scribble(f.tone), strokeWidth: 1.5, hachureGap: 6 }}>
                  <DoodleIcon name={f.icon} size={26} fallback={<span aria-hidden="true">✶</span>} />
                </Sketch>
                <h3 className="font-head text-lg leading-6 font-bold">{f.title}</h3>
              </div>
              <p className="text-lg leading-7 text-ink/80">{f.body}</p>
            </Sketch>
          </motion.li>
        ))}
      </ul>
    </Section>
  );
}

const SETUP = `git clone ${REPO} && cd okf-sdk
uv sync
cd packages/okf-web2 && bun install && bun run build && cd -
uv run okf-web --static packages/okf-web2/dist`;

function Start() {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(SETUP); setCopied(true); setTimeout(() => setCopied(false), 1800); } catch { /* no clipboard */ }
  };
  return (
    <Section id="start" title="Wake Okie up (about 2 minutes)" kicker="Get started">
      <div className="grid items-center gap-10 md:grid-cols-[1.5fr_1fr]">
        <Reveal className="min-w-0">
          <p className="mb-4 text-lg">You need <a href="https://docs.astral.sh/uv/">uv</a> and <a href="https://bun.sh/">Bun</a>. Then:</p>
          <Sketch className="relative -rotate-[0.5deg] bg-note px-5 py-4" rough={{ strokeWidth: 2 }}>
            <pre className="m-0 overflow-x-auto font-mono text-sm leading-7 whitespace-pre text-ink">{SETUP}</pre>
            <button onClick={copy} className="doodle-btn absolute top-2 right-3 cursor-pointer text-sm text-ink/70 hover:text-ink">
              {copied ? "copied ✓" : "copy"}
            </button>
          </Sketch>
          <p className="mt-4 text-lg">Open <b>http://127.0.0.1:8765</b>, make a workspace, make a notebook, write something. Okie takes it from there.</p>
          <p className="mt-2 text-lg">Want your AI to help? The <a href={DOCS}>boring page</a> shows how to plug in the MCP server.</p>
        </Reveal>
        <Reveal x={80} delay={0.2}><Okie pose="writing" size={360} className="mx-auto w-full max-w-[360px]" /></Reveal>
      </div>
    </Section>
  );
}

const FAQ: [string, ReactNode][] = [
  ["Why a snail?", "Slow, carries its house around, leaves a trail. Also nobody else wanted the job."],
  ["Where do my notes actually go?", <>Plain markdown files in <code>~/.okf/workspaces/</code>. Edit them anywhere, commit them, grep them.</>],
  ["Can my AI assistant use it?", "Yes. Plug the MCP server into Claude (or any MCP client) and it reads and writes the same notebooks you see in the app."],
  ["Is it safe to put on the internet?", "No. There’s no login. Keep it on your own machine. Okie is a homebody."],
  ["Does it cost anything?", "No. Okie works for free. Okie has made some poor life choices."],
  ["Why is Okie so tired?", "You’d be tired too."],
];

function Faq() {
  return (
    <Section id="faq" title="Questions people ask Okie" kicker="FAQ">
      <Decor name="balloon" className="top-0 right-6 w-20 rotate-6" />
      <Reveal className="grid gap-4 md:grid-cols-2">
        {FAQ.map(([q, a], i) => (
          // the outline sits on a wrapper: a closed <details> hides every child except its <summary>
          <Sketch key={q} className="self-start bg-paper" style={{ rotate: `${i % 2 ? 0.6 : -0.6}deg` }} rough={{ strokeWidth: 1.8 }}>
            <details className="px-5 py-3">
              <summary className="cursor-pointer font-head text-lg font-bold marker:text-ink/50">{q}</summary>
              <p className="mt-2 text-lg leading-7 text-ink/80">{a}</p>
            </details>
          </Sketch>
        ))}
      </Reveal>
    </Section>
  );
}

function Footer() {
  return (
    <footer className="relative mx-auto max-w-6xl pr-5 pl-[72px] md:px-5 pt-6 pb-16 text-center">
      <Decor name="stars-cluster" className="top-4 left-[18%] w-28" />
      <Decor name="flower" className="bottom-10 left-4 w-20" />
      <Decor name="house" className="right-4 bottom-8 w-32" />
      <div className="relative mx-auto w-fit">
        <Okie pose="asleep" size={240} />
        <span aria-hidden="true" className="zzz absolute top-6 right-2 font-hand text-3xl text-ink/50"><i>z</i><i>z</i><i>Z</i></span>
      </div>
      <p className="mt-2 font-head text-2xl font-bold">Okie is going back to sleep now.</p>
      <p className="text-lg text-ink/70">Come back when you forget something. You will.</p>
      <div className="mt-6 flex flex-wrap justify-center gap-5">
        <LinkBtn href="#start" tone="green">Fine, let’s go</LinkBtn>
        <LinkBtn href={REPO} tone="pink" tilt={1} className="star-btn"><span className="inline-flex items-center gap-1.5"><StarIcon />Star it on GitHub</span></LinkBtn>
        <LinkBtn href={DOCS} tone="blue" tilt={-0.8}>The boring docs</LinkBtn>
      </div>
      <p className="mt-10 text-sm text-ink/50">Made with crayons and a sigh. Built on the Open Knowledge Format.</p>
    </footer>
  );
}

/** Okie crawls along the bottom of the screen as you scroll, leaving a dotted slime trail. */
function Trail() {
  const { scrollYProgress } = useScroll();
  const p = useSpring(scrollYProgress, { stiffness: 70, damping: 20 });
  const width = useTransform(p, (v) => `${v * 100}%`);
  const left = useTransform(p, (v) => `calc(${v * 100}% - ${v * 64}px)`);
  if (!markUrl) return null;
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-x-0 bottom-0 z-20 hidden h-11 md:block">
      <motion.div style={{ width }} className="absolute bottom-1.5 left-0 border-b-[3px] border-dotted border-ink/25" />
      <motion.img src={markUrl} alt="" style={{ left }} className="absolute bottom-0 h-11 w-16 -scale-x-100 object-contain" />
    </div>
  );
}

/** The marketing page: same notebook paper, same snail, more sighing. */
export function Landing() {
  return (
    <MotionConfig reducedMotion="user">
      <Trail />
      <Nav />
      <main className="overflow-x-clip">
        <Hero />
        <Pains />
        <How />
        <Everyone />
        <Look />
        <Features />
        <Start />
        <Faq />
      </main>
      <Footer />
    </MotionConfig>
  );
}
