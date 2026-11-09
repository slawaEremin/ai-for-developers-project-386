import js from '@eslint/js';
import vue from 'eslint-plugin-vue';
import ts from 'typescript-eslint';

export default ts.config(
  { ignores: ['dist/**', 'src/api/generated/**'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  ...vue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: ts.parser } },
    rules: {
      // Имена в TypeScript, включая DOM-типы в Vue, проверяет vue-tsc.
      'no-undef': 'off',
      'vue/multi-word-component-names': 'off',
    },
  },
);
