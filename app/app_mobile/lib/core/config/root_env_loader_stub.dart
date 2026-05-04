import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Web 등 IO 미지원 환경 — 파일 없음.
Future<void> loadRepoRootDotEnv() async {
  dotenv.loadFromString(envString: '', isOptional: true);
}
