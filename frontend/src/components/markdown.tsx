import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// The agent's report is markdown (tables, bold, headers) -- this renders it
// with plain Tailwind utility classes rather than pulling in a typography
// plugin, since it's a handful of element types.
export function AgentMarkdown({ content }: { content: string }) {
  return (
    <div className="text-sm leading-relaxed space-y-3">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (props) => <h2 className="text-lg font-semibold mt-4 mb-2" {...props} />,
          h2: (props) => <h3 className="text-base font-semibold mt-4 mb-2" {...props} />,
          h3: (props) => <h4 className="text-sm font-semibold mt-3 mb-1" {...props} />,
          p: (props) => <p className="mb-2" {...props} />,
          ul: (props) => <ul className="list-disc pl-5 space-y-1 mb-2" {...props} />,
          ol: (props) => <ol className="list-decimal pl-5 space-y-1 mb-2" {...props} />,
          strong: (props) => <strong className="font-semibold" {...props} />,
          table: (props) => (
            <div className="overflow-x-auto my-3 rounded-md border">
              <table className="w-full text-xs" {...props} />
            </div>
          ),
          thead: (props) => <thead className="bg-muted" {...props} />,
          th: (props) => (
            <th className="px-3 py-2 text-left font-medium border-b" {...props} />
          ),
          td: (props) => <td className="px-3 py-2 border-b tabular-nums" {...props} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
