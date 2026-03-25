self.llm = OllamaClient()

self.tools = {
    "web": PlaywrightTool(),
    "sql": None,  # plus tard
}