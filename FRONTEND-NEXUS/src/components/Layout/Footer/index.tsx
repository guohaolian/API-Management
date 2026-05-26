import React from "react";
import styles from "./index.module.less";

const Footer: React.FC = () => {
    return (
        <div className={styles.footer}>
            <span>
                Copyright © 2025 - {new Date().getFullYear()}{" "}
                <a
                    href="mailto:15947513567charlie@gmail.com"
                    style={{ color: "#007bff", textDecoration: "none" }}
                >
                    Guo HL
                </a>
                . All Rights Reserved.
            </span>
        </div>
    );
};

export default Footer;
