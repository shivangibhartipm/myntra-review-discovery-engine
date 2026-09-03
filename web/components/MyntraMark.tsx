export function MyntraMark({ className = "h-10 w-auto" }: { className?: string }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/myntra-logo.png"
      alt="Myntra"
      className={className}
      decoding="async"
    />
  );
}
