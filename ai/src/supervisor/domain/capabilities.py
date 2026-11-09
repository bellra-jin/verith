"""Connected capability does not promise stock support, auth or remaining usage."""
VIEWS = ('flow', 'technical', 'fundamental', 'macro', 'industry', 'news', 'overview')

def capability_list():
    return [dict(view=v, connected=v == 'flow', reason='connected_flow' if v == 'flow' else 'news_excluded' if v == 'news' else 'not_connected') for v in VIEWS]
