// ESLint flat config — next/core-web-vitals + next/typescript (구 .eslintrc.json 대체)
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals'
import nextTypescript from 'eslint-config-next/typescript'

const eslintConfig = [
  ...nextCoreWebVitals,
  ...nextTypescript,
]

export default eslintConfig
