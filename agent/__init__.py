

#AXA_IA/__axa/agent_cv/agent/__init__.py

self.llm = OllamaClient()

self.tools = {
    "web": PlaywrightTool(),
    "sql": None,  # plus tard
}