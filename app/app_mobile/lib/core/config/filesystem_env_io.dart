import 'dart:io';

import 'package:path/path.dart' as p;

import 'env_parser.dart';

/// Monorepo 루트 `.env` + `dart_defines/local.env` (호스트 파일시스템).
Future<Map<String, String>> loadFilesystemEnvMaps() async {
  final merged = <String, String>{};

  final rootEnv = await _findRepoRootDotEnv();
  if (rootEnv != null) {
    merged.addAll(parseEnvContent(await rootEnv.readAsString()));
  }

  final localEnv = await _findLocalEnvFile();
  if (localEnv != null) {
    merged.addAll(parseEnvContent(await localEnv.readAsString()));
  }

  return merged;
}

Future<File?> _findLocalEnvFile() async {
  var dir = Directory.current;
  for (var i = 0; i < 24; i++) {
    final direct = File(p.join(dir.path, 'dart_defines', 'local.env'));
    if (await direct.exists()) return direct;

    final fromRepoRoot = File(
      p.join(dir.path, 'app', 'app_mobile', 'dart_defines', 'local.env'),
    );
    if (await fromRepoRoot.exists()) return fromRepoRoot;

    final parent = dir.parent;
    if (parent.path == dir.path) break;
    dir = parent;
  }
  return null;
}

Future<File?> _findRepoRootDotEnv() async {
  var dir = Directory.current;
  for (var i = 0; i < 24; i++) {
    final envFile = File(p.join(dir.path, '.env'));
    final composeYaml = File(p.join(dir.path, 'docker-compose.yaml'));
    final composeYml = File(p.join(dir.path, 'docker-compose.yml'));
    final hasCompose =
        await composeYaml.exists() || await composeYml.exists();
    if (hasCompose && await envFile.exists()) {
      return envFile;
    }
    final parent = dir.parent;
    if (parent.path == dir.path) break;
    dir = parent;
  }
  return null;
}
