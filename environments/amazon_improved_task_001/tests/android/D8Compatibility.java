/** Exercises the anonymous inner-class parameter metadata emitted by javac 21. */
public class D8Compatibility {
    public Runnable action() {
        return new Runnable() {
            @Override public void run() {
                System.out.println(D8Compatibility.this.toString());
            }
        };
    }
}
