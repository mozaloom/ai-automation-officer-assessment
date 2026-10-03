import ChatPanel from "@/components/app/ChatPanel";

export default function AssistantPage() {
  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-text-dark">Availability assistant</h1>
        <p className="text-sm text-text-gray">Ask in plain language. Every answer is built from the matching POS records, which are shown with it.</p>
      </header>
      <ChatPanel />
    </div>
  );
}
