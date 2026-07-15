export function QuickStart() {
  return (
    <div className="bg-card rounded-xl p-6 border border-border shadow-sahara">
      <h3 className="text-lg font-semibold text-foreground mb-3">Quick Start</h3>
      <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
        <li>Generate a token in the Token Management section below</li>
        <li>Copy the config from the tab above</li>
        <li>Add it to your agent&apos;s MCP settings file</li>
        <li>Restart your agent</li>
      </ol>
    </div>
  );
}
