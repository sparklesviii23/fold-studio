/** Atom picks use live native keys, never author-number guesses across models. */
export function atomPickSelection(current:readonly string[],picked:string,additive:boolean,available:ReadonlySet<string>):string[]{
 if(!available.has(picked))throw new Error('The picked atom is no longer in the scientific scene.');
 return additive?[...new Set([...current.filter(key=>available.has(key)),picked])]:[picked];
}
