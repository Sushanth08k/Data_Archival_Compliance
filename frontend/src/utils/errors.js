/**
 * Helper to safely extract human-readable error messages from Axios / FastAPI responses.
 * Prevents React rendering crashes when FastAPI returns a 422 array of validation errors.
 */

export function getErrorMessage(err, fallback = 'An unexpected error occurred') {
  if (!err) return fallback;

  const detail = err.response?.data?.detail;
  if (detail) {
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') return item;
          const loc = item.loc ? `${item.loc.slice(1).join('.')}: ` : '';
          return `${loc}${item.msg || item.message || JSON.stringify(item)}`;
        })
        .join('; ');
    }
    if (typeof detail === 'object') {
      return detail.msg || detail.message || JSON.stringify(detail);
    }
    return String(detail);
  }

  return err.response?.data?.message || err.message || fallback;
}
