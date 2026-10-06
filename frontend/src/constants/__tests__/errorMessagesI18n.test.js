import { describe, test, expect, vi, afterEach } from 'vitest';
import i18n from '../../i18n/config';
import {
  ERROR_MESSAGES,
  getErrorCategory,
  getUserFriendlyError,
  formatErrorWithContext,
} from '../errorMessages';

const SPANISH = {
  'errors:form.submissionFailed': 'Error al guardar el formulario.',
  'errors:upload.failed': 'No se pudo subir el archivo.',
};

describe('localized error messages', () => {
  afterEach(() => vi.restoreAllMocks());

  const useSpanish = () =>
    vi
      .spyOn(i18n, 't')
      .mockImplementation(
        (key, options) =>
          SPANISH[key] ??
          (options?.defaultValue || key).replace(
            /\{\{(\w+)\}\}/g,
            (m, name) => options?.[name] ?? m
          )
      );

  test('catalog values resolve in the active language', () => {
    useSpanish();
    expect(ERROR_MESSAGES.FORM_SUBMISSION_FAILED).toBe(
      'Error al guardar el formulario.'
    );
  });

  test('getUserFriendlyError returns the translated message with its code', () => {
    useSpanish();
    expect(getUserFriendlyError(new Error('boom'), 'save')).toBe(
      'Error al guardar el formulario. (Error: FORM-400)'
    );
  });

  test('getErrorCategory recognizes translated messages', () => {
    useSpanish();
    expect(getErrorCategory('Error al guardar el formulario.')).toBe('form');
  });

  test('context messages use translation keys with interpolation', () => {
    const spy = useSpanish();
    formatErrorWithContext(ERROR_MESSAGES.UPLOAD_FAILED, 'a.pdf');
    expect(spy).toHaveBeenCalledWith(
      'errors:upload.failedNamed',
      expect.objectContaining({ name: 'a.pdf' })
    );
  });
});
