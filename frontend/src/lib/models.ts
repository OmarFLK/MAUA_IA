export function modelDisplayName(model?: string) {
  if (!model) return 'Modelo não informado'
  return model.replace(/^google\//, '').replace('gemma-3-27b', 'Gemma 3 27B')
}
