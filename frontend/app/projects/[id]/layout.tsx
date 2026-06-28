export default function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  return (
    <div className="min-h-screen">
      <header className="border-b px-6 py-3">
        <div className="flex items-center gap-6">
          <span className="font-bold text-lg">Rexgent</span>
          <span className="text-sm text-muted-foreground">
            Project: {params.id}
          </span>
        </div>
      </header>
      <div className="px-6 pt-4">{children}</div>
    </div>
  );
}
