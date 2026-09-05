import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";


// The agent's report is markdown (tables, bold, headers) — rendered
// with our own CSS classes (see .agent-markdown in index.css) rather
// than a typography plugin, since it's a handful of element types.
export default function AgentMarkdown({
    content,
}: {
    content: string;
}) {

    return (
        <div className="agent-markdown">

            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    h1: (props) => <h2 {...props} />,
                    h2: (props) => <h3 {...props} />,
                    h3: (props) => <h4 {...props} />,
                    p: (props) => <p {...props} />,
                    ul: (props) => <ul {...props} />,
                    ol: (props) => <ol {...props} />,
                    strong: (props) => <strong {...props} />,
                    table: (props) => (
                        <div className="agent-markdown-table-wrap">
                            <table {...props} />
                        </div>
                    ),
                    thead: (props) => <thead {...props} />,
                    th: (props) => <th {...props} />,
                    td: (props) => <td {...props} />,
                }}
            >
                {content}
            </ReactMarkdown>

        </div>
    );
}
