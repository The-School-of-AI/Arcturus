
import json
import ast

def _ensure_parsed_value(value):
    if not isinstance(value, str):
        if isinstance(value, list):
            return [_ensure_parsed_value(item) for item in value]
        if isinstance(value, dict):
            return {k: _ensure_parsed_value(v) for k, v in value.items()}
        return value
    
    stripped = value.strip()
    
    if (stripped.startswith('[') and stripped.endswith(']')) or \
       (stripped.startswith('{') and stripped.endswith('}')):
        try:
            parsed = json.loads(stripped)
            return _ensure_parsed_value(parsed)
        except (json.JSONDecodeError, TypeError):
            pass
        
        try:
            parsed = ast.literal_eval(stripped)
            return _ensure_parsed_value(parsed)
        except (ValueError, SyntaxError):
            pass
    
    return value

# The string from session.json
raw_str = "['https://breakingglobe.com/index.php/2025/04/10/ipl-year-wise-revenue-growth-2008-2/', 'https://www.statista.com/topics/4543/indian-premier-league-ipl/', 'https://economictimes.indiatimes.com/news/sports/ipl-a-bigger-hit-revenues-surge/articleshow/116114612.cms', 'https://www.business-standard.com/cricket/ipl/ipl-franchises-revenue-more-than-double-bcci-surplus-jumps-to-rs-5-120-cr-124090600893_1.html', 'https://www.timesnownews.com/business-economy/industry/how-ipl-makes-money-breaking-down-multi-billion-dollar-indian-premier-league-cricket-business-article-110461871', 'https://medium.com/@theunitedindian500/ipl-revenue-per-year-4d740fa8a77e', 'https://finvests.in/ipl-winners-2008-to-2025-titles-captains-earnings/', 'https://www.kreedon.com/indian-premier-league-ipl-revenue-growth-breaking-down-the-numbers', 'https://en.wikipedia.org/wiki/List_of_Indian_Premier_League_records_and_statistics', 'https://blog.privatecircle.co/the-business-behind-the-ipl-sponsorships-revenues-and-the-rise-of-cricket-economics-fy24-deep-dive/']"

parsed = _ensure_parsed_value(raw_str)
print(f"Type: {type(parsed)}")
print(f"Value: {parsed}")
if isinstance(parsed, list):
    print(f"Length: {len(parsed)}")
else:
    print("FAILED TO PARSE AS LIST")
