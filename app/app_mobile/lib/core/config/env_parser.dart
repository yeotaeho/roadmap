/// `.env` 형식 문자열을 key-value 맵으로 파싱.
Map<String, String> parseEnvContent(String content) {
  final result = <String, String>{};
  for (final rawLine in content.split('\n')) {
    final line = rawLine.trim();
    if (line.isEmpty || line.startsWith('#')) continue;
    final eq = line.indexOf('=');
    if (eq < 1) continue;
    final key = line.substring(0, eq).trim();
    var value = line.substring(eq + 1).trim();
    if (value.length >= 2) {
      final q = value[0];
      if ((q == '"' || q == "'") && value.endsWith(q)) {
        value = value.substring(1, value.length - 1);
      }
    }
    if (key.isNotEmpty) {
      result[key] = value;
    }
  }
  return result;
}
