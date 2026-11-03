
document.addEventListener("DOMContentLoaded", function () {

    // Find the navigation menu.
    const navLinks = document.getElementById("navLinks");

    // Find the menu button.
    const menuButton = document.getElementById("menuButton");

    // Check that the elements exist.
    if (navLinks && menuButton) {

        // Listen for a button click.
        menuButton.addEventListener("click", function () {

            // Toggle the open class.
            const isOpen = navLinks.classList.toggle("open");

            // Update the accessibility state.
            menuButton.setAttribute(
                "aria-expanded",
                String(isOpen)
            );

        });
    }

});
