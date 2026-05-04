import 'dart:io';

import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:path/path.dart' as p;

/// `docker-compose.yaml`과 같은 디렉터리의 `.env`를 찾아 로드합니다.
/// 실행 시 [Directory.current]에서 상위로 올라가며 탐색합니다.
Future<void> loadRepoRootDotEnv() async {
  final file = await _findDockerComposeSiblingDotEnv();
  if (file != null && await file.exists()) {
    final content = await file.readAsString();
    if (content.trim().isEmpty) {
      dotenv.loadFromString(envString: '', isOptional: true);
      return;
    }
    dotenv.loadFromString(envString: content);
    return;
  }
  dotenv.loadFromString(envString: '', isOptional: true);
}

Future<File?> _findDockerComposeSiblingDotEnv() async {
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
