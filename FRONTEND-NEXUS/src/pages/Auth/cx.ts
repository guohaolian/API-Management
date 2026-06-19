/** Tiny classname combiner for CSS Modules. */
export default function cx(
    ...classes: (string | undefined | false | null)[]
): string {
    return classes.filter(Boolean).join(" ");
}
